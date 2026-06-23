"""Jinja2 报告渲染。"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _rate_percent(value: Any, *, digits: int = 0) -> str:
    percent = (_to_decimal(value) * Decimal("100")).quantize(Decimal("1"))
    if digits > 0:
        percent = (_to_decimal(value) * Decimal("100")).quantize(
            Decimal("1." + ("0" * digits))
        )
    return f"{percent}%"


def _rate_width(value: Any) -> int:
    percent = int((_to_decimal(value) * Decimal("100")).to_integral_value())
    return max(0, min(100, percent))


def _score_width(value: Any) -> int:
    score = int(_to_decimal(value).to_integral_value())
    return max(0, min(100, score))


def _source_type_label(source_type: str | None) -> str:
    labels = {
        "web": "网页来源",
        "official": "官网/官方来源",
        "media": "媒体报道",
        "social": "社交/论坛",
        "video": "视频平台",
        "ecommerce": "电商/OTA",
    }
    return labels.get((source_type or "").lower(), "未分类来源")


def _domain_from_url(url: str | None) -> str:
    if not url:
        return ""
    host = urlparse(url).hostname or ""
    return host[4:] if host.startswith("www.") else host


def _summary_metric_rate(row: PlatformAnalysis, metric_code: str) -> str:
    metrics = ((row.summary_json or {}).get("metrics") or {})
    metric = metrics.get(metric_code) or {}
    value = metric.get("rate")
    if value is None:
        return "0.0000"
    return str(Decimal(str(value)).quantize(Decimal("0.0001")))


def _platform_score(platform: dict[str, Any]) -> int:
    mention = _to_decimal(platform["brand_mention_rate"])
    top1 = _to_decimal(platform["brand_top1_mention_rate"])
    top3 = _to_decimal(platform["brand_top3_mention_rate"])
    completeness = _to_decimal(platform["data_completeness_rate"])
    score = (
        mention * Decimal("45")
        + top1 * Decimal("30")
        + top3 * Decimal("15")
        + completeness * Decimal("10")
    )
    return _score_width(score)


def _build_platform_scoreboard(platforms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for platform in platforms:
        score = _platform_score(platform)
        rows.append(
            {
                "platform_code": platform["platform_code"],
                "score": score,
                "score_width": score,
                "valid_answer_count": platform["valid_answer_count"],
                "brand_mention_percent": _rate_percent(platform["brand_mention_rate"]),
                "brand_mention_width": _rate_width(platform["brand_mention_rate"]),
                "brand_top1_percent": _rate_percent(platform["brand_top1_mention_rate"]),
                "brand_top3_percent": _rate_percent(platform["brand_top3_mention_rate"]),
                "avg_rank_label": _avg_rank_label(platform),
                "sentiment_label": _sentiment_label(platform),
                "summary": (platform["summary_json"] or {}).get("platform_summary", ""),
            }
        )
    rows.sort(key=lambda item: (-item["score"], item["platform_code"]))
    return rows


def _avg_rank_label(platform: dict[str, Any]) -> str:
    prompt_rows = platform.get("prompt_competitiveness_summary") or []
    ranks = [
        _to_decimal(item.get("target_rank"))
        for item in prompt_rows
        if item.get("target_rank") is not None
    ]
    if not ranks:
        return "暂无排名"
    avg = sum(ranks, Decimal("0")) / Decimal(len(ranks))
    return f"#{avg.quantize(Decimal('0.1'))}"


def _sentiment_label(platform: dict[str, Any]) -> str:
    rate = _to_decimal(platform["brand_mention_rate"])
    if rate >= Decimal("0.7"):
        return "正向/高可见"
    if rate >= Decimal("0.35"):
        return "中性/待强化"
    return "弱曝光"


def _build_prompt_scene_cards(
    platforms: list[dict[str, Any]],
    prompt_map: dict[int, str],
) -> list[dict[str, Any]]:
    cards = []
    for platform in platforms:
        for item in platform["prompt_competitiveness_summary"]:
            score = _score_width(item.get("competitiveness_score") or 0)
            rank = item.get("target_rank")
            cards.append(
                {
                    "platform_code": platform["platform_code"],
                    "prompt_id": item.get("prompt_id"),
                    "prompt_text": prompt_map.get(item.get("prompt_id"), ""),
                    "score": score,
                    "score_width": score,
                    "target_rank": rank,
                    "rank_label": f"第 {rank} 梯队" if rank else "未提及",
                    "tone": "good" if score >= 70 else "weak",
                }
            )
    cards.sort(key=lambda item: (-item["score"], item["platform_code"], item["prompt_id"] or 0))
    return cards


def _build_source_type_distribution(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, int] = defaultdict(int)
    for source in sources:
        totals[_source_type_label(source.get("source_type"))] += int(
            source.get("citation_count") or 0
        )
    total = sum(totals.values())
    rows = []
    for label, count in totals.items():
        rate = Decimal(count) / Decimal(total) if total else Decimal("0")
        rows.append(
            {
                "label": label,
                "citation_count": count,
                "share_percent": _rate_percent(rate),
                "share_width": _rate_width(rate),
            }
        )
    rows.sort(key=lambda item: (-item["citation_count"], item["label"]))
    return rows


def _build_top_source_cards(
    sources: list[dict[str, Any]],
    answers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    domains = {
        source["domain"]: {
            "domain": source["domain"],
            "source_name": source.get("source_name") or source["domain"],
            "source_type": _source_type_label(source.get("source_type")),
            "citation_count": int(source.get("citation_count") or 0),
            "share_percent": _rate_percent(source.get("share_rate")),
            "prompts": set(),
            "platforms": set(),
            "examples": [],
        }
        for source in sources
    }
    for answer in answers:
        for citation in answer["citations"]:
            domain = citation.get("domain") or _domain_from_url(citation.get("url"))
            if not domain or domain not in domains:
                continue
            card = domains[domain]
            if answer.get("prompt_text"):
                card["prompts"].add(answer["prompt_text"])
            card["platforms"].add(answer["platform_code"])
            if len(card["examples"]) < 2:
                card["examples"].append(
                    {
                        "title": citation.get("title") or domain,
                        "url": citation.get("url") or "",
                    }
                )
    cards = []
    for card in domains.values():
        cards.append(
            {
                **card,
                "prompts": sorted(card["prompts"])[:5],
                "platforms": sorted(card["platforms"])[:6],
            }
        )
    cards.sort(key=lambda item: (-item["citation_count"], item["domain"]))
    return cards[:10]


def _build_recommendations(
    platforms: list[dict[str, Any]],
    prompt_cards: list[dict[str, Any]],
    source_cards: list[dict[str, Any]],
) -> list[dict[str, str]]:
    recommendations = []
    for platform in platforms:
        suggestions = (platform.get("improvement_json") or {}).get("suggestions") or []
        for item in suggestions:
            title = item.get("title")
            detail = item.get("detail")
            if title and detail:
                recommendations.append(
                    {
                        "title": title,
                        "basis": f"{platform['platform_code']} 平台 Agent 洞察",
                        "action": detail,
                    }
                )

    weak_platforms = [
        item["platform_code"]
        for item in platforms
        if _to_decimal(item["brand_mention_rate"]) < Decimal("0.5")
    ]
    if weak_platforms:
        recommendations.append(
            {
                "title": "补齐低可见平台内容覆盖",
                "basis": "部分平台品牌提及率低于 50%",
                "action": f"优先为 {', '.join(weak_platforms[:4])} 补充品牌介绍、场景问答与权威引用素材。",
            }
        )

    weak_prompts = [item for item in prompt_cards if item["score"] < 70]
    if weak_prompts:
        recommendations.append(
            {
                "title": "优先攻克低表现问题场景",
                "basis": f"{len(weak_prompts)} 个平台-问题组合未进入高竞争力区间",
                "action": "围绕低分问题补充可被引用的专题页面、FAQ 和案例内容，提升 AI 回答中的推荐优先级。",
            }
        )

    if not source_cards:
        recommendations.append(
            {
                "title": "建立可被 AI 引用的权威信源",
                "basis": "本轮未形成稳定引用来源",
                "action": "建设官网栏目、媒体稿与结构化问答页，为模型提供可追溯的品牌证据。",
            }
        )
    else:
        recommendations.append(
            {
                "title": "放大高权重来源的品牌信号",
                "basis": f"TOP 来源 {source_cards[0]['domain']} 已被多次引用",
                "action": "对高频来源页面补充品牌卖点、核心场景和差异化表述，放大既有信源权重。",
            }
        )
    return recommendations[:8]


def _build_diagnosis(
    *,
    target_brand_name: str,
    platforms: list[dict[str, Any]],
    scoreboard: list[dict[str, Any]],
    prompt_cards: list[dict[str, Any]],
    source_cards: list[dict[str, Any]],
    recommendations: list[dict[str, str]],
) -> dict[str, Any]:
    overall_score = (
        round(sum(item["score"] for item in scoreboard) / len(scoreboard))
        if scoreboard
        else 0
    )
    if overall_score >= 80:
        level = "整体表现领先"
    elif overall_score >= 60:
        level = "整体表现稳定"
    elif overall_score >= 40:
        level = "存在提升空间"
    else:
        level = "亟需优化"

    best = scoreboard[0]["platform_code"] if scoreboard else "暂无平台"
    worst = scoreboard[-1]["platform_code"] if scoreboard else "暂无平台"
    strengths = []
    risks = []
    if scoreboard:
        strengths.append(f"{best} 平台综合得分最高，品牌可见度基础较好。")
        if scoreboard[0]["brand_mention_width"] >= 70:
            strengths.append("核心平台已形成稳定品牌提及，可作为内容优化样板。")
        if source_cards:
            strengths.append(f"{source_cards[0]['domain']} 等来源已进入 AI 引用链路。")
        if scoreboard[-1]["brand_mention_width"] < 50:
            risks.append(f"{worst} 平台品牌提及偏弱，用户优先获取品牌信息的概率较低。")
    if prompt_cards and any(item["score"] < 70 for item in prompt_cards):
        risks.append("部分问题场景未形成高竞争力回答，需要补齐场景内容与权威证据。")
    if not source_cards:
        risks.append("引用来源不足，报告缺少可追溯的权威内容支撑。")
    if not risks:
        risks.append("当前主要风险集中在持续维护排名与扩展更多问题场景覆盖。")

    summary = (
        f"{target_brand_name} 本轮 GEO 综合得分 {overall_score}，{level}。"
        f"建议围绕平台差异、问题场景和高权重信源持续优化。"
    )
    return {
        "overall_score": overall_score,
        "overall_score_width": overall_score,
        "level": level,
        "summary": summary,
        "strengths": strengths[:4],
        "risks": risks[:4],
        "recommendation_count": len(recommendations),
    }


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
                "brand_top1_mention_rate": _summary_metric_rate(
                    row,
                    "brand_top1_mention_rate",
                )
                if row.summary_json
                else _decimal(row.brand_first_rate),
                "brand_top3_mention_rate": _summary_metric_rate(
                    row,
                    "brand_top3_mention_rate",
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

    platform_scoreboard = _build_platform_scoreboard(platforms)
    prompt_scene_cards = _build_prompt_scene_cards(platforms, prompt_map)
    source_type_distribution = _build_source_type_distribution(sources)
    top_source_cards = _build_top_source_cards(sources, answers)
    action_recommendations = _build_recommendations(
        platforms,
        prompt_scene_cards,
        top_source_cards,
    )
    diagnosis = _build_diagnosis(
        target_brand_name=base["target_brand_name"],
        platforms=platforms,
        scoreboard=platform_scoreboard,
        prompt_cards=prompt_scene_cards,
        source_cards=top_source_cards,
        recommendations=action_recommendations,
    )

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
        "diagnosis": diagnosis,
        "platform_scoreboard": platform_scoreboard,
        "prompt_scene_cards": prompt_scene_cards,
        "source_type_distribution": source_type_distribution,
        "top_source_cards": top_source_cards,
        "action_recommendations": action_recommendations,
    }


# 使用 Jinja2 模板将上下文渲染为 Markdown 报告。
def render_markdown(context: dict[str, Any]) -> str:
    template = _jinja_env.get_template("report.md.j2")
    return template.render(**context)


# 使用 Jinja2 模板将上下文渲染为 HTML 报告。
def render_html(context: dict[str, Any]) -> str:
    template = _jinja_env.get_template("report.html.j2")
    return template.render(**context, html_escape=html_escape)
