"""Jinja2 报告渲染。"""

from __future__ import annotations

from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.geo_monitoring.models import MonitorProject, MonitorRun, Prompt, QueryTask
from app.geo_monitoring.services.analysis import (
    AgentExecution,
    PlatformAnalysis,
    SourceStat,
    load_run_context,
)

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "report"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(enabled_extensions=("html", "j2")),
)


# 对文本进行 HTML 转义，供模板安全输出。
def html_escape(text: str | None) -> str:
    return escape(text or "", quote=True)


# 将 Decimal 指标格式化为字符串，空值输出 "0"。
def _decimal(value: Decimal | None) -> str:
    if value is None:
        return "0"
    return str(value)


# 聚合运行、平台分析、来源统计与回答数据，构建报告渲染上下文。
def build_report_context(db: Session, run_id: int) -> dict[str, Any]:
    base = load_run_context(db, run_id)
    run: MonitorRun = base["run"]
    project: MonitorProject = base["project"]

    # 加载各平台分析结果
    platform_rows = list(
        db.execute(
            select(PlatformAnalysis).where(
                PlatformAnalysis.run_id == run_id,
                PlatformAnalysis.is_deleted.is_(False),
            )
        )
        .scalars()
        .all()
    )
    # 加载引用来源统计
    source_rows = list(
        db.execute(
            select(SourceStat).where(
                SourceStat.run_id == run_id,
                SourceStat.is_deleted.is_(False),
            )
        )
        .scalars()
        .all()
    )
    # 加载成功的 Agent 语义分析输出
    agent_rows = list(
        db.execute(
            select(AgentExecution).where(
                AgentExecution.run_id == run_id,
                AgentExecution.is_deleted.is_(False),
                AgentExecution.status == "success",
            )
        )
        .scalars()
        .all()
    )

    # 关联 Prompt 文本以便在报告中展示问题内容
    prompt_rows = list(
        db.execute(
            select(Prompt, QueryTask)
            .join(QueryTask, QueryTask.prompt_id == Prompt.id)
            .where(
                QueryTask.run_id == run_id,
                QueryTask.is_deleted.is_(False),
                Prompt.is_deleted.is_(False),
            )
        )
        .all()
    )
    prompt_map: dict[int, str] = {}
    for prompt, _task in prompt_rows:
        prompt_map[prompt.id] = prompt.prompt_text

    answers = []
    # 组装每条回答及其引用列表
    for answer in base["answers"]:
        answers.append(
            {
                "platform_code": answer.platform_code,
                "prompt_id": answer.prompt_id,
                "prompt_text": prompt_map.get(answer.prompt_id, ""),
                "raw_text": answer.raw_text,
                "raw_text_html": html_escape(answer.raw_text),
                "model_name": answer.model_name,
                "latency_ms": answer.latency_ms,
                "citations": [
                    {
                        "title": citation.title,
                        "url": citation.url,
                        "domain": citation.domain,
                        "source_type": citation.source_type,
                    }
                    for citation in answer.citations
                ],
            }
        )

    platforms = []
    for row in platform_rows:
        platforms.append(
            {
                "platform_code": row.platform_code,
                "status": row.status,
                "valid_answer_count": row.valid_answer_count,
                "data_completeness_rate": _decimal(row.data_completeness_rate),
                "brand_mention_rate": _decimal(row.brand_mention_rate),
                "brand_first_rate": _decimal(row.brand_first_rate),
                "brand_first_among_mentions_rate": _decimal(
                    row.brand_first_among_mentions_rate
                ),
                "top_competitors": row.top_competitors or [],
                "top_sources": row.top_sources or [],
                "prompt_competitiveness_summary": row.prompt_competitiveness_summary
                or [],
                "improvement_json": row.improvement_json or {},
                "summary_json": row.summary_json or {},
            }
        )

    sources = [
        {
            "platform_code": row.platform_code,
            "domain": row.domain,
            "source_name": row.source_name,
            "source_type": row.source_type,
            "citation_count": row.citation_count,
            "brand_related_count": row.brand_related_count,
            "share_rate": _decimal(row.share_rate),
            "rank_no": row.rank_no,
        }
        for row in source_rows
    ]

    agent_insights = [
        {
            "platform_code": row.platform_code,
            "agent_code": row.agent_code,
            "output_json": row.output_json or {},
            "model_name": row.model_name,
        }
        for row in agent_rows
    ]

    return {
        "project": {
            "id": project.id,
            "name": project.project_name,
            "industry": project.industry,
            "report_title": project.report_title or project.project_name,
            "report_subtitle": project.report_subtitle or "",
            "official_domain": project.official_domain or "",
        },
        "run": {
            "id": run.id,
            "run_no": run.run_no,
            "status": run.status,
            "analysis_status": run.analysis_status,
            "prompt_set_version": run.prompt_set_version,
            "valid_answer_count": run.valid_answer_count,
            "data_completeness_rate": _decimal(run.data_completeness_rate),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        },
        "target_brand_name": base["target_brand_name"],
        "platforms": platforms,
        "sources": sources,
        "answers": answers,
        "agent_insights": agent_insights,
    }


# 使用 Jinja2 模板将上下文渲染为 Markdown 报告。
def render_markdown(context: dict[str, Any]) -> str:
    template = _jinja_env.get_template("report.md.j2")
    return template.render(**context)


# 使用 Jinja2 模板将上下文渲染为 HTML 报告。
def render_html(context: dict[str, Any]) -> str:
    template = _jinja_env.get_template("report.html.j2")
    return template.render(**context, html_escape=html_escape)
