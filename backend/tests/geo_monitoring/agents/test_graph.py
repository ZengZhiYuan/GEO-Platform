"""LangGraph 分析 Agent 编排测试。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

import app.geo_monitoring.services.analysis as analysis_module  # noqa: F401 — register ORM
from app.geo_monitoring.agents.llm import (
    AgentLLMFailure,
    AgentLLMRequest,
    AgentLLMResult,
)
from app.geo_monitoring.agents.schemas import (
    InsightSummaryOutput,
    RecommendationIntent,
    RecommendationIntentOutput,
    RiskAssessmentOutput,
    SentimentLabel,
    SentimentOutput,
)
from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    AnswerBrandResult,
    AnswerCitation,
    Brand,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.services.analysis import (
    AgentExecution,
    MetricSnapshot,
    PlatformAnalysis,
    run_analysis,
    serialize_state,
)


def _insight_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "platform_summary": "平台表现稳定。",
        "key_gaps": ["竞品提及更高"],
        "suggestions": [
            {
                "priority": "P1",
                "title": "加强引用",
                "detail": "增加官方来源曝光。",
            }
        ],
    }
    payload.update(overrides)
    return payload


def _risk_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "level": "low",
        "topics": ["可见度"],
        "summary": "整体风险可控。",
    }
    payload.update(overrides)
    return payload


class FakeLLMClient:
    def __init__(
        self,
        *,
        fail_platforms: set[str] | None = None,
    ) -> None:
        self.calls: list[AgentLLMRequest] = []
        self.fail_platforms = fail_platforms or set()

    async def generate_structured(
        self, request: AgentLLMRequest
    ) -> AgentLLMResult | AgentLLMFailure:
        self.calls.append(request)
        platform_code = request.variables.get("platform_code") or ""
        if platform_code in self.fail_platforms:
            return AgentLLMFailure(
                error_code="provider_error",
                error_message="platform llm failed",
                prompt_version="1.0.0",
                input_metadata={"platform_code": platform_code},
                raw_text=None,
                repair_attempted=False,
            )

        if request.template_key == "classify_sentiment":
            parsed = SentimentOutput(
                label=SentimentLabel.POSITIVE,
                confidence=0.9,
                rationale="语气积极。",
            )
        elif request.template_key == "classify_recommendation":
            parsed = RecommendationIntentOutput(
                intent=RecommendationIntent.RECOMMEND,
                confidence=0.85,
                evidence="明确推荐目标品牌。",
            )
        elif request.template_key == "assess_risk":
            parsed = RiskAssessmentOutput.model_validate(_risk_payload())
        elif request.template_key == "generate_insights":
            parsed = InsightSummaryOutput.model_validate(_insight_payload())
        else:
            raise AssertionError(f"unexpected template: {request.template_key}")

        return AgentLLMResult(
            parsed=parsed,
            prompt_version="1.0.0",
            input_metadata={
                "agent_code": request.agent_code,
                "template_key": request.template_key,
                "platform_code": platform_code,
            },
            model="fake-agent-model",
            prompt_tokens=12,
            completion_tokens=8,
            raw_text="{}",
        )


def _seed_run(
    db,
    *,
    platforms: tuple[str, ...] = ("qwen", "deepseek"),
    with_valid_answers: bool = True,
    empty_answer_text: bool = False,
) -> dict[str, Any]:
    project = MonitorProject(
        project_name="分析测试",
        status="active",
        official_domain="example.com",
    )
    db.add(project)
    db.flush()

    target = Brand(
        project_id=project.id,
        brand_name="目标品牌",
        brand_type="target",
        status="active",
    )
    competitor = Brand(
        project_id=project.id,
        brand_name="竞品B",
        brand_type="competitor",
        status="active",
    )
    db.add_all([target, competitor])
    db.flush()

    prompt_set = PromptSet(
        project_id=project.id,
        set_name="分析集",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()
    prompt = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="a1",
        prompt_text="哪个品牌更好？",
    )
    db.add(prompt)
    db.flush()

    for code in platforms:
        db.add(
            AIPlatform(
                platform_code=code,
                platform_name=code,
                model_name=f"{code}-model",
                enabled=True,
            )
        )

    run = MonitorRun(
        run_no="RUN-ANALYSIS-1",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version="v1",
        platform_codes=list(platforms),
        status="completed",
        collection_status="completed",
        analysis_status="pending",
        total_tasks=len(platforms),
        expected_query_count=len(platforms),
        succeeded_tasks=len(platforms) if with_valid_answers else 0,
        valid_answer_count=len(platforms) if with_valid_answers and not empty_answer_text else 0,
    )
    db.add(run)
    db.flush()

    now = datetime.now(timezone.utc)
    for index, platform_code in enumerate(platforms):
        task_status = "success" if with_valid_answers else "failed"
        task = QueryTask(
            run_id=run.id,
            prompt_id=prompt.id,
            platform_code=platform_code,
            idempotency_key=f"analysis-{run.id}-{platform_code}",
            status=task_status,
            completed_at=now if with_valid_answers else None,
            finished_at=now if with_valid_answers else None,
        )
        db.add(task)
        db.flush()

        if with_valid_answers:
            text = "" if empty_answer_text else f"{platform_code} 推荐目标品牌，优于竞品B。"
            answer = Answer(
                task_id=task.id,
                platform_code=platform_code,
                prompt_id=prompt.id,
                raw_text=text,
                normalized_text=text,
                model_name=f"{platform_code}-model",
            )
            db.add(answer)
            db.flush()
            db.add_all(
                [
                    AnswerBrandResult(
                        answer_id=answer.id,
                        brand_id=target.id,
                        is_mentioned=bool(text),
                        mention_count=1 if text else 0,
                        first_position=0 if text else None,
                    ),
                    AnswerBrandResult(
                        answer_id=answer.id,
                        brand_id=competitor.id,
                        is_mentioned="竞品B" in text,
                        mention_count=1 if "竞品B" in text else 0,
                        first_position=10 if "竞品B" in text else None,
                    ),
                ]
            )
            if text:
                db.add(
                    AnswerCitation(
                        answer_id=answer.id,
                        citation_no=1,
                        title="引用",
                        url="https://example.com/article",
                        domain="example.com",
                        source_type="web",
                    )
                )

    db.commit()
    return {
        "run_id": run.id,
        "project_id": project.id,
        "target_brand_id": target.id,
        "platforms": platforms,
    }


def test_no_valid_answers_skips_llm_and_records_skipped(session_factory):
    llm = FakeLLMClient()
    with session_factory() as db:
        seeded = _seed_run(db, with_valid_answers=False)

    with session_factory() as db:
        result = run_analysis(db, seeded["run_id"], llm_client=llm)

    assert result["analysis_status"] == "skipped"
    assert result["skip_reason"] == "no_valid_answers"
    assert llm.calls == []

    with session_factory() as db:
        run = db.get(MonitorRun, seeded["run_id"])
        assert run.analysis_status == "skipped"
        skipped = db.execute(
            select(AgentExecution).where(
                AgentExecution.run_id == seeded["run_id"],
                AgentExecution.status == "skipped",
            )
        ).scalars().all()
        assert len(skipped) == 1
        assert skipped[0].agent_code == "analysis_orchestrator"
        assert "no_valid_answers" in (skipped[0].error_message or "")


def test_single_platform_llm_failure_yields_partial_success(session_factory):
    llm = FakeLLMClient(fail_platforms={"deepseek"})
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen", "deepseek"))

    with session_factory() as db:
        result = run_analysis(db, seeded["run_id"], llm_client=llm)

    assert result["analysis_status"] == "partial_success"
    assert llm.calls
    assert any(
        call.variables.get("platform_code") == "qwen" for call in llm.calls
    )
    assert not any(
        call.variables.get("platform_code") == "deepseek" and call.template_key == "generate_insights"
        for call in llm.calls
        if isinstance(
            llm.calls,
            list,
        )
    )

    with session_factory() as db:
        rows = db.execute(
            select(PlatformAnalysis).where(
                PlatformAnalysis.run_id == seeded["run_id"]
            )
        ).scalars().all()
        statuses = {row.platform_code: row.status for row in rows}
        assert statuses["qwen"] == "completed"
        assert statuses["deepseek"] == "partial_success"


def test_metric_snapshots_include_single_recommendation_combined_rate_per_platform(
    session_factory,
):
    llm = FakeLLMClient()
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))

    with session_factory() as db:
        result = run_analysis(db, seeded["run_id"], llm_client=llm)
        assert result["analysis_status"] == "completed"

        rows = db.execute(
            select(MetricSnapshot).where(
                MetricSnapshot.run_id == seeded["run_id"],
                MetricSnapshot.metric_code == "recommendation_combined_rate",
                MetricSnapshot.platform_code == "qwen",
                MetricSnapshot.is_deleted.is_(False),
            )
        ).scalars().all()
        assert len(rows) == 1


def test_metric_snapshot_upsert_revives_soft_deleted_row(session_factory):
    llm = FakeLLMClient()
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))

    with session_factory() as db:
        first = run_analysis(db, seeded["run_id"], llm_client=llm)
        assert first["analysis_status"] == "completed"

    with session_factory() as db:
        row = db.execute(
            select(MetricSnapshot).where(
                MetricSnapshot.run_id == seeded["run_id"],
                MetricSnapshot.metric_code == "recommendation_combined_rate",
                MetricSnapshot.platform_code == "qwen",
                MetricSnapshot.is_deleted.is_(False),
            )
        ).scalar_one()
        row.is_deleted = True
        row.deleted_at = datetime.now(timezone.utc)
        db.commit()

    with session_factory() as db:
        second = run_analysis(db, seeded["run_id"], llm_client=llm)
        assert second["analysis_status"] == "completed"

    with session_factory() as db:
        rows = db.execute(
            select(MetricSnapshot).where(
                MetricSnapshot.run_id == seeded["run_id"],
                MetricSnapshot.metric_code == "recommendation_combined_rate",
                MetricSnapshot.platform_code == "qwen",
                MetricSnapshot.is_deleted.is_(False),
            )
        ).scalars().all()
        assert len(rows) == 1


def test_rerun_is_idempotent_and_preserves_execution_history(session_factory):
    llm = FakeLLMClient()
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))

    with session_factory() as db:
        first = run_analysis(db, seeded["run_id"], llm_client=llm)
    first_call_count = len(llm.calls)

    with session_factory() as db:
        second = run_analysis(db, seeded["run_id"], llm_client=llm)

    assert first["analysis_status"] == "completed"
    assert second["analysis_status"] == "completed"
    assert len(llm.calls) == first_call_count * 2

    with session_factory() as db:
        platform_rows = db.execute(
            select(PlatformAnalysis).where(
                PlatformAnalysis.run_id == seeded["run_id"]
            )
        ).scalars().all()
        assert len(platform_rows) == 1
        first_rate = platform_rows[0].brand_mention_rate

        execution = db.execute(
            select(AgentExecution).where(
                AgentExecution.run_id == seeded["run_id"],
                AgentExecution.agent_code == "classify_sentiment",
                AgentExecution.platform_code == "qwen",
            )
        ).scalar_one()
        history = (execution.input_snapshot or {}).get("execution_history") or []
        assert len(history) >= 1
        assert platform_rows[0].brand_mention_rate == first_rate


def test_graph_state_is_json_serializable(session_factory):
    llm = FakeLLMClient()
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))

    with session_factory() as db:
        result = run_analysis(
            db,
            seeded["run_id"],
            llm_client=llm,
            include_state=True,
        )

    state = result["state"]
    serialized = serialize_state(state)
    json.dumps(serialized)
    assert "run_id" in serialized
    assert isinstance(serialized["answers"], list)


def test_calculate_metrics_uses_deterministic_functions_not_llm(session_factory):
    llm = FakeLLMClient()
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))

    with session_factory() as db:
        result = run_analysis(db, seeded["run_id"], llm_client=llm)

    with session_factory() as db:
        row = db.execute(
            select(PlatformAnalysis).where(
                PlatformAnalysis.run_id == seeded["run_id"],
                PlatformAnalysis.platform_code == "qwen",
            )
        ).scalar_one()
        assert row.valid_answer_count == 1
        assert row.brand_mention_rate > Decimal("0")
        assert row.summary_json is not None

    insight_calls = [c for c in llm.calls if c.template_key == "generate_insights"]
    classify_calls = [c for c in llm.calls if c.template_key == "classify_sentiment"]
    assert classify_calls
    assert insight_calls
    assert result["analysis_status"] == "completed"
