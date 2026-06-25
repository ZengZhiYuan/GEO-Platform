"""项目看板汇总：总体指标与分平台指标统计。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessException
from app.geo_monitoring.analysis.dto import AnswerInput, BrandMentionInput
from app.geo_monitoring.analysis.brands import (
    compute_average_mention_rank,
    compute_brand_mention_count,
    compute_sentiment_rates,
    compute_share_of_voice,
)
from app.geo_monitoring.analysis.metrics import (
    _collect_brand_ids,
    compute_brand_rank_rate,
    compute_brand_visibility,
    compute_rate,
)
from app.geo_monitoring.models import AIPlatform, Answer, Brand, MonitorRun, QueryTask
from app.geo_monitoring.services.analysis import MetricSnapshot, PlatformAnalysis
from app.geo_monitoring.services.projects import require_active_project
from app.geo_monitoring.services.runs import get_run

_OVERVIEW_RECENT_QUESTIONS_LIMIT = 5
_OVERVIEW_COMPETITOR_PREVIEW_LIMIT = 5
_OVERVIEW_SOURCE_PREVIEW_LIMIT = 5

_RUN_TERMINAL = frozenset({"completed", "partial_success", "failed", "cancelled"})
_ANALYZED = frozenset({"completed", "partial_success"})


def _decimal_str(value: Decimal | None, *, quant: Decimal | None = None) -> str:
    if value is None:
        return "0"
    if quant is not None:
        return str(value.quantize(quant))
    return str(value)


def _summary_metric(row: PlatformAnalysis, metric_code: str) -> dict[str, Any]:
    metrics = ((row.summary_json or {}).get("metrics") or {})
    return metrics.get(metric_code) or {}


def _summary_metric_count(row: PlatformAnalysis, metric_code: str) -> int:
    metric = _summary_metric(row, metric_code)
    return int(metric.get("numerator") or 0)


def _summary_metric_rate(row: PlatformAnalysis, metric_code: str) -> str:
    metric = _summary_metric(row, metric_code)
    value = metric.get("rate")
    if value is None:
        return "0.0000"
    return str(Decimal(str(value)).quantize(Decimal("0.0001")))


def _rate_metric_payload(
    *,
    metric_code: str,
    numerator: int,
    denominator: int,
    platform_code: str | None = None,
) -> dict[str, Any]:
    rate = compute_rate(numerator, denominator)
    return {
        "metric_code": metric_code,
        "platform_code": platform_code,
        "numerator": str(numerator),
        "denominator": str(denominator),
        "metric_value": _decimal_str(rate),
    }


def _platform_analysis_payload(row: PlatformAnalysis) -> dict[str, Any]:
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
        "brand_top1_mention_count": _summary_metric_count(
            row,
            "brand_top1_mention_rate",
        )
        or row.brand_first_count,
        "brand_top1_mention_rate": _summary_metric_rate(
            row,
            "brand_top1_mention_rate",
        )
        if row.summary_json
        else str(row.brand_first_rate),
        "brand_top3_mention_count": _summary_metric_count(
            row,
            "brand_top3_mention_rate",
        ),
        "brand_top3_mention_rate": _summary_metric_rate(
            row,
            "brand_top3_mention_rate",
        ),
        "brand_top10_mention_rate": _summary_metric_rate(
            row,
            "brand_top10_mention_rate",
        ),
        "average_mention_rank": _summary_metric_scalar(row, "average_mention_rank"),
        "share_of_voice": _summary_metric_scalar(row, "share_of_voice"),
        "brand_mention_total_count": _summary_metric_total_count(
            row,
            "brand_mention_total_count",
        ),
        "positive_rate": _summary_metric_rate(row, "positive_rate"),
        "neutral_rate": _summary_metric_rate(row, "neutral_rate"),
        "negative_rate": _summary_metric_rate(row, "negative_rate"),
        "top_competitors": row.top_competitors,
        "top_sources": row.top_sources,
        "prompt_competitiveness_summary": row.prompt_competitiveness_summary,
        "improvement_json": row.improvement_json,
        "summary_json": row.summary_json,
    }


def _metric_snapshot_payload(row: MetricSnapshot) -> dict[str, Any]:
    return {
        "metric_code": row.metric_code,
        "platform_code": row.platform_code,
        "brand_id": row.brand_id,
        "numerator": _decimal_str(row.numerator),
        "denominator": _decimal_str(row.denominator),
        "metric_value": _decimal_str(row.metric_value),
        "prompt_set_version": row.prompt_set_version,
        "snapshot_at": row.snapshot_at.isoformat(),
        "completeness_rate": str(row.completeness_rate),
    }


def _run_summary(run: MonitorRun) -> dict[str, Any]:
    return {
        "run_id": run.id,
        "run_no": run.run_no,
        "status": run.status,
        "collection_status": run.collection_status,
        "analysis_status": run.analysis_status,
        "platform_codes": list(run.platform_codes or []),
        "valid_answer_count": run.valid_answer_count,
        "data_completeness_rate": str(run.data_completeness_rate),
        "total_tasks": run.total_tasks,
        "succeeded_tasks": run.succeeded_tasks,
        "failed_tasks": run.failed_tasks,
        "cancelled_tasks": run.cancelled_tasks,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def _load_platform_catalog(db: Session, platform_codes: list[str]) -> dict[str, str]:
    if not platform_codes:
        return {}
    rows = list(
        db.execute(
            select(AIPlatform).where(
                AIPlatform.platform_code.in_(platform_codes),
                AIPlatform.is_deleted.is_(False),
            )
        )
        .scalars()
        .all()
    )
    return {row.platform_code: row.platform_name for row in rows}


def _load_collection_stats(db: Session, run_id: int) -> dict[str, dict[str, int]]:
    rows = list(
        db.execute(
            select(
                QueryTask.platform_code,
                QueryTask.status,
                func.count().label("count"),
            )
            .where(
                QueryTask.run_id == run_id,
                QueryTask.is_deleted.is_(False),
            )
            .group_by(QueryTask.platform_code, QueryTask.status)
        ).all()
    )
    stats: dict[str, dict[str, int]] = {}
    for platform_code, status, count in rows:
        bucket = stats.setdefault(
            platform_code,
            {
                "total_tasks": 0,
                "succeeded_tasks": 0,
                "failed_tasks": 0,
                "cancelled_tasks": 0,
            },
        )
        bucket["total_tasks"] += int(count)
        if status == "success":
            bucket["succeeded_tasks"] += int(count)
        elif status == "failed":
            bucket["failed_tasks"] += int(count)
        elif status == "cancelled":
            bucket["cancelled_tasks"] += int(count)
    return stats


def _summary_metric_scalar(row: PlatformAnalysis, metric_code: str) -> str | None:
    metric = _summary_metric(row, metric_code)
    if metric in (None, {}):
        return None
    if isinstance(metric, (int, float, Decimal, str)):
        return str(metric)
    if not isinstance(metric, dict):
        return str(metric)
    value = metric.get("rate")
    if value is None:
        value = metric.get("metric")
    if value is None:
        return None
    return str(value)


def _summary_metric_total_count(row: PlatformAnalysis, metric_code: str) -> int:
    metric = _summary_metric(row, metric_code)
    if isinstance(metric, int):
        return metric
    if isinstance(metric, dict):
        if metric.get("numerator") is not None:
            return int(metric["numerator"])
        if metric.get("metric") is not None:
            return int(metric["metric"])
    return 0


def _aggregate_metric_snapshots(
    snapshots: list[MetricSnapshot],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, int]] = {}
    for row in snapshots:
        if row.prompt_id is not None or row.brand_id is not None:
            continue
        bucket = grouped.setdefault(
            row.metric_code,
            {"numerator": 0, "denominator": 0},
        )
        bucket["numerator"] += int(row.numerator or 0)
        bucket["denominator"] += int(row.denominator or 0)
    return [
        _rate_metric_payload(
            metric_code=metric_code,
            numerator=values["numerator"],
            denominator=values["denominator"],
            platform_code=None,
        )
        for metric_code, values in sorted(grouped.items())
    ]


def _aggregate_extended_from_analysis(rows: list[PlatformAnalysis]) -> dict[str, Any]:
    if not rows:
        return {}
    total_mention_count = 0
    top10_num = 0
    top10_den = 0
    pos_num = 0
    pos_den = 0
    neu_num = 0
    neu_den = 0
    neg_num = 0
    neg_den = 0
    for row in rows:
        total_mention_count += _summary_metric_total_count(
            row,
            "brand_mention_total_count",
        )
        top10 = _summary_metric(row, "brand_top10_mention_rate")
        top10_num += int(top10.get("numerator") or 0)
        top10_den += int(top10.get("denominator") or 0)
        pos_metric = _summary_metric(row, "positive_rate")
        pos_num += int(pos_metric.get("numerator") or 0)
        pos_den += int(pos_metric.get("denominator") or 0)
        neu_metric = _summary_metric(row, "neutral_rate")
        neu_num += int(neu_metric.get("numerator") or 0)
        neu_den += int(neu_metric.get("denominator") or 0)
        neg_metric = _summary_metric(row, "negative_rate")
        neg_num += int(neg_metric.get("numerator") or 0)
        neg_den += int(neg_metric.get("denominator") or 0)

    return {
        "brand_mention_total_count": total_mention_count or None,
        "brand_top10_mention_rate": _decimal_str(
            compute_rate(top10_num, top10_den),
            quant=Decimal("0.0001"),
        )
        if top10_den > 0
        else None,
        "positive_rate": _decimal_str(compute_rate(pos_num, pos_den), quant=Decimal("0.0001"))
        if pos_den > 0
        else None,
        "neutral_rate": _decimal_str(compute_rate(neu_num, neu_den), quant=Decimal("0.0001"))
        if neu_den > 0
        else None,
        "negative_rate": _decimal_str(compute_rate(neg_num, neg_den), quant=Decimal("0.0001"))
        if neg_den > 0
        else None,
    }


def _aggregate_analysis_summary(rows: list[PlatformAnalysis]) -> dict[str, Any] | None:
    if not rows:
        return None

    valid = sum(row.valid_answer_count for row in rows)
    mentions = sum(row.brand_mention_count for row in rows)
    first = sum(row.brand_first_count for row in rows)
    top1 = sum(
        _summary_metric_count(row, "brand_top1_mention_rate") or row.brand_first_count
        for row in rows
    )
    top3 = sum(_summary_metric_count(row, "brand_top3_mention_rate") for row in rows)
    top10 = sum(_summary_metric_count(row, "brand_top10_mention_rate") for row in rows)
    extended = _aggregate_extended_from_analysis(rows)
    if valid > 0:
        completeness = sum(
            row.data_completeness_rate * row.valid_answer_count for row in rows
        ) / Decimal(valid)
    else:
        completeness = Decimal("0")

    return {
        "scope": "all",
        "valid_answer_count": valid,
        "brand_mention_count": mentions,
        "brand_mention_rate": _decimal_str(compute_rate(mentions, valid)),
        "brand_first_count": first,
        "brand_first_rate": _decimal_str(compute_rate(first, valid)),
        "brand_top1_mention_count": top1,
        "brand_top1_mention_rate": _decimal_str(compute_rate(top1, valid)),
        "brand_top3_mention_count": top3,
        "brand_top3_mention_rate": _decimal_str(compute_rate(top3, valid)),
        "brand_top10_mention_count": top10,
        "brand_top10_mention_rate": extended.get("brand_top10_mention_rate")
        or _decimal_str(compute_rate(top10, valid)),
        "data_completeness_rate": _decimal_str(
            completeness.quantize(Decimal("0.0001"))
        ),
        "brand_mention_total_count": extended.get("brand_mention_total_count"),
        "positive_rate": extended.get("positive_rate"),
        "neutral_rate": extended.get("neutral_rate"),
        "negative_rate": extended.get("negative_rate"),
        "metrics": [],
    }


def _select_latest_run(db: Session, project_id: int) -> MonitorRun | None:
    analyzed = db.execute(
        select(MonitorRun)
        .where(
            MonitorRun.project_id == project_id,
            MonitorRun.is_deleted.is_(False),
            MonitorRun.analysis_status.in_(_ANALYZED),
        )
        .order_by(MonitorRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if analyzed is not None:
        return analyzed

    return db.execute(
        select(MonitorRun)
        .where(
            MonitorRun.project_id == project_id,
            MonitorRun.is_deleted.is_(False),
            MonitorRun.status.in_(_RUN_TERMINAL),
        )
        .order_by(MonitorRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def build_project_dashboard(
    db: Session,
    project_id: int,
    *,
    run_id: int | None = None,
) -> dict[str, Any]:
    """构建项目看板：总体汇总 + 分平台采集/分析指标。"""
    require_active_project(db, project_id)

    if run_id is not None:
        run = get_run(db, run_id)
        if run.project_id != project_id:
            raise BusinessException(code=40400, message="监测运行不存在")
    else:
        run = _select_latest_run(db, project_id)

    if run is None:
        return {
            "project_id": project_id,
            "latest_run": None,
            "summary": None,
            "platforms": [],
        }

    platform_codes = list(run.platform_codes or [])
    catalog = _load_platform_catalog(db, platform_codes)
    collection_stats = _load_collection_stats(db, run.id)

    analysis_rows = list(
        db.execute(
            select(PlatformAnalysis).where(
                PlatformAnalysis.run_id == run.id,
                PlatformAnalysis.is_deleted.is_(False),
            )
        )
        .scalars()
        .all()
    )
    analysis_by_code = {row.platform_code: row for row in analysis_rows}

    snapshots = list(
        db.execute(
            select(MetricSnapshot).where(
                MetricSnapshot.run_id == run.id,
                MetricSnapshot.is_deleted.is_(False),
                MetricSnapshot.prompt_id.is_(None),
                MetricSnapshot.brand_id.is_(None),
            )
        )
        .scalars()
        .all()
    )
    snapshots_by_platform: dict[str, list[MetricSnapshot]] = {}
    for row in snapshots:
        if not row.platform_code:
            continue
        snapshots_by_platform.setdefault(row.platform_code, []).append(row)

    summary = _aggregate_analysis_summary(analysis_rows)
    if summary is not None:
        summary["metrics"] = _aggregate_metric_snapshots(snapshots)

    platforms: list[dict[str, Any]] = []
    ordered_codes = platform_codes or sorted(
        set(collection_stats) | set(analysis_by_code)
    )
    for code in ordered_codes:
        analysis_row = analysis_by_code.get(code)
        platform_snapshots = snapshots_by_platform.get(code, [])
        platforms.append(
            {
                "platform_code": code,
                "platform_name": catalog.get(code, code),
                "collection": collection_stats.get(
                    code,
                    {
                        "total_tasks": 0,
                        "succeeded_tasks": 0,
                        "failed_tasks": 0,
                        "cancelled_tasks": 0,
                    },
                ),
                "analysis": _platform_analysis_payload(analysis_row)
                if analysis_row is not None
                else None,
                "metrics": [
                    _metric_snapshot_payload(item) for item in platform_snapshots
                ],
            }
        )

    return {
        "project_id": project_id,
        "latest_run": _run_summary(run),
        "summary": summary,
        "platforms": platforms,
    }


def _normalize_platform_codes(platform_codes: list[str] | None) -> list[str] | None:
    if not platform_codes:
        return None
    return list(dict.fromkeys(code.strip() for code in platform_codes if code.strip()))


def _resolve_platform_codes(
    run: MonitorRun,
    platform_codes: list[str] | None,
) -> list[str]:
    if platform_codes:
        return platform_codes
    return list(run.platform_codes or [])


def _load_target_brand(db: Session, project_id: int) -> Brand | None:
    return db.execute(
        select(Brand).where(
            Brand.project_id == project_id,
            Brand.brand_type == "target",
            Brand.is_deleted.is_(False),
            Brand.status == "active",
        )
    ).scalar_one_or_none()


def _extract_extended_kpis_from_competitor_data(
    competitor_data: dict[str, Any],
) -> dict[str, Any]:
    """扩展 KPI 与竞品分析服务保持一致，避免跨平台 SOV 被错误加权平均。"""
    if not competitor_data.get("has_analysis_data"):
        return {
            "average_rank": None,
            "share_of_voice": None,
            "brand_mention_total_count": None,
        }
    kpis = competitor_data.get("kpis") or {}
    mention_count = kpis.get("mention_count")
    return {
        "average_rank": kpis.get("average_rank"),
        "share_of_voice": kpis.get("share_of_voice"),
        "brand_mention_total_count": mention_count,
    }


def _load_overview_answers(
    db: Session,
    *,
    run_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[Answer]:
    conditions: list[Any] = [
        QueryTask.run_id == run_id,
        QueryTask.is_deleted.is_(False),
        Answer.is_deleted.is_(False),
    ]
    if platform_codes:
        conditions.append(Answer.platform_code.in_(platform_codes))
    if start_at is not None:
        conditions.append(Answer.collected_at >= start_at)
    if end_at is not None:
        conditions.append(Answer.collected_at <= end_at)
    return list(
        db.execute(
            select(Answer)
            .join(QueryTask, QueryTask.id == Answer.task_id)
            .where(*conditions)
            .options(
                selectinload(Answer.brand_results),
                selectinload(Answer.task),
            )
            .order_by(Answer.id)
        )
        .scalars()
        .all()
    )


def _answer_input_from_row(answer: Answer) -> AnswerInput:
    task_status = answer.task.status if answer.task is not None else "failed"
    return AnswerInput(
        answer_id=answer.id,
        prompt_id=answer.prompt_id,
        platform_code=answer.platform_code,
        task_status=task_status,
        normalized_text=answer.normalized_text or answer.raw_text or "",
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
    )


def _summary_from_filtered_answers(
    answers: list[Answer],
    *,
    target_brand_id: int,
    brand_ids: tuple[int, ...] | None = None,
) -> dict[str, Any] | None:
    answer_inputs = [_answer_input_from_row(answer) for answer in answers]
    visibility = compute_brand_visibility(
        answer_inputs,
        target_brand_id=target_brand_id,
    )
    top1 = compute_brand_rank_rate(
        answer_inputs,
        target_brand_id=target_brand_id,
        max_rank=1,
    )
    top3 = compute_brand_rank_rate(
        answer_inputs,
        target_brand_id=target_brand_id,
        max_rank=3,
    )
    top10 = compute_brand_rank_rate(
        answer_inputs,
        target_brand_id=target_brand_id,
        max_rank=10,
    )
    if visibility.denominator == 0:
        return None

    resolved_brand_ids = brand_ids or _collect_brand_ids(
        answer_inputs,
        seed_ids=(target_brand_id,),
    )
    sov = compute_share_of_voice(answer_inputs, brand_ids=resolved_brand_ids).get(
        target_brand_id
    )
    sentiment_rates = compute_sentiment_rates(answer_inputs, target_brand_id)
    average_rank = compute_average_mention_rank(answer_inputs, target_brand_id)

    return {
        "scope": "all",
        "valid_answer_count": visibility.denominator,
        "brand_mention_count": visibility.numerator,
        "brand_mention_rate": _decimal_str(visibility.rate),
        "brand_top1_mention_count": top1.numerator,
        "brand_top1_mention_rate": _decimal_str(top1.rate),
        "brand_top3_mention_count": top3.numerator,
        "brand_top3_mention_rate": _decimal_str(top3.rate),
        "brand_top10_mention_count": top10.numerator,
        "brand_top10_mention_rate": _decimal_str(top10.rate),
        "average_rank": _decimal_str(average_rank, quant=Decimal("0.1"))
        if average_rank is not None
        else None,
        "share_of_voice": _decimal_str(sov, quant=Decimal("0.0001")),
        "brand_mention_total_count": compute_brand_mention_count(
            answer_inputs,
            target_brand_id,
        ),
        "positive_rate": _decimal_str(sentiment_rates["positive_rate"].rate),
        "neutral_rate": _decimal_str(sentiment_rates["neutral_rate"].rate),
        "negative_rate": _decimal_str(sentiment_rates["negative_rate"].rate),
    }


def _empty_kpis_payload() -> dict[str, Any]:
    return {
        "brand_mention_rate": None,
        "brand_top1_mention_rate": None,
        "brand_top3_mention_rate": None,
        "brand_top10_mention_rate": None,
        "valid_answer_count": None,
        "brand_mention_count": None,
        "average_rank": None,
        "share_of_voice": None,
        "brand_mention_total_count": None,
        "positive_rate": None,
        "neutral_rate": None,
        "negative_rate": None,
    }


def _summary_to_kpis_payload(
    summary: dict[str, Any] | None,
    *,
    extended: dict[str, Any],
) -> dict[str, Any]:
    if summary is None:
        return _empty_kpis_payload()
    return {
        "brand_mention_rate": summary.get("brand_mention_rate"),
        "brand_top1_mention_rate": summary.get("brand_top1_mention_rate"),
        "brand_top3_mention_rate": summary.get("brand_top3_mention_rate"),
        "brand_top10_mention_rate": summary.get("brand_top10_mention_rate")
        or extended.get("brand_top10_mention_rate"),
        "valid_answer_count": summary.get("valid_answer_count"),
        "brand_mention_count": summary.get("brand_mention_count"),
        "average_rank": summary.get("average_rank") or extended.get("average_rank"),
        "share_of_voice": summary.get("share_of_voice") or extended.get("share_of_voice"),
        "brand_mention_total_count": extended.get("brand_mention_total_count")
        or summary.get("brand_mention_total_count"),
        "positive_rate": summary.get("positive_rate") or extended.get("positive_rate"),
        "neutral_rate": summary.get("neutral_rate") or extended.get("neutral_rate"),
        "negative_rate": summary.get("negative_rate") or extended.get("negative_rate"),
    }


def _empty_competitor_preview() -> dict[str, Any]:
    return {
        "boards": {
            "mention_rate": [],
            "average_rank": [],
            "mention_count": [],
        }
    }


def _competitor_preview_payload(
    competitor_data: dict[str, Any],
    *,
    limit: int,
) -> dict[str, Any]:
    boards = competitor_data.get("boards") or {}
    return {
        "boards": {
            "mention_rate": list(boards.get("mention_rate") or [])[:limit],
            "average_rank": list(boards.get("average_rank") or [])[:limit],
            "mention_count": list(boards.get("mention_count") or [])[:limit],
        }
    }


def _source_preview_payload(source_data: dict[str, Any]) -> dict[str, Any]:
    sites = source_data.get("sites") or {}
    return {
        "items": list(sites.get("items") or []),
        "total": int(sites.get("total") or 0),
    }


def _recent_questions_preview_payload(
    conversation_data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "items": list(conversation_data.get("items") or []),
        "total": int(conversation_data.get("total") or 0),
    }


def _empty_overview_payload(project_id: int) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "run_id": None,
        "kpis": _empty_kpis_payload(),
        "platforms": [],
        "competitor_preview": _empty_competitor_preview(),
        "source_preview": {"items": [], "total": 0},
        "recent_questions": {"items": [], "total": 0},
    }


def build_dashboard_overview(
    db: Session,
    project_id: int,
    *,
    run_id: int | None = None,
    platform_codes: list[str] | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> dict[str, Any]:
    """构建数据大盘首屏：KPI、平台表现与竞品/信源/问题预览。"""
    from app.geo_monitoring.services import competitor_analysis as competitor_analysis_service
    from app.geo_monitoring.services import conversations as conversations_service
    from app.geo_monitoring.services import source_analysis as source_analysis_service

    require_active_project(db, project_id)
    platform_codes = _normalize_platform_codes(platform_codes)

    if run_id is not None:
        run = get_run(db, run_id)
        if run.project_id != project_id:
            raise BusinessException(code=40400, message="监测运行不存在")
    else:
        run = _select_latest_run(db, project_id)

    if run is None:
        return _empty_overview_payload(project_id)

    selected_codes = _resolve_platform_codes(run, platform_codes)
    catalog = _load_platform_catalog(db, selected_codes)
    collection_stats = _load_collection_stats(db, run.id)

    analysis_conditions = [
        PlatformAnalysis.run_id == run.id,
        PlatformAnalysis.is_deleted.is_(False),
    ]
    if platform_codes:
        analysis_conditions.append(PlatformAnalysis.platform_code.in_(platform_codes))
    analysis_rows = list(
        db.execute(select(PlatformAnalysis).where(*analysis_conditions))
        .scalars()
        .all()
    )
    analysis_by_code = {row.platform_code: row for row in analysis_rows}

    competitor_data = competitor_analysis_service.get_competitor_analysis(
        db,
        project_id,
        run_id=run.id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        brand_scope="top5",
    )

    use_time_filter = start_at is not None or end_at is not None
    target_brand = _load_target_brand(db, project_id)
    if use_time_filter and target_brand is not None:
        filtered_answers = _load_overview_answers(
            db,
            run_id=run.id,
            platform_codes=platform_codes,
            start_at=start_at,
            end_at=end_at,
        )
        summary = _summary_from_filtered_answers(
            filtered_answers,
            target_brand_id=target_brand.id,
        )
    else:
        summary = _aggregate_analysis_summary(analysis_rows)

    extended = _extract_extended_kpis_from_competitor_data(competitor_data)
    kpis = _summary_to_kpis_payload(summary, extended=extended)

    platforms: list[dict[str, Any]] = []
    ordered_codes = selected_codes or sorted(
        set(collection_stats) | set(analysis_by_code)
    )
    for code in ordered_codes:
        analysis_row = analysis_by_code.get(code)
        platforms.append(
            {
                "platform_code": code,
                "platform_name": catalog.get(code, code),
                "analysis": _platform_analysis_payload(analysis_row)
                if analysis_row is not None
                else None,
            }
        )

    source_data = source_analysis_service.get_source_analysis(
        db,
        project_id,
        run_id=run.id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        page=1,
        page_size=_OVERVIEW_SOURCE_PREVIEW_LIMIT,
    )
    conversation_data = conversations_service.list_conversation_questions(
        db,
        project_id,
        run_id=run.id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        page=1,
        page_size=_OVERVIEW_RECENT_QUESTIONS_LIMIT,
    )

    return {
        "project_id": project_id,
        "run_id": run.id,
        "kpis": kpis,
        "platforms": platforms,
        "competitor_preview": _competitor_preview_payload(
            competitor_data,
            limit=_OVERVIEW_COMPETITOR_PREVIEW_LIMIT,
        ),
        "source_preview": _source_preview_payload(source_data),
        "recent_questions": _recent_questions_preview_payload(conversation_data),
    }
