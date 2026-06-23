"""项目看板汇总：总体指标与分平台指标统计。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.analysis.metrics import compute_rate
from app.geo_monitoring.models import AIPlatform, MonitorRun, QueryTask
from app.geo_monitoring.services.analysis import MetricSnapshot, PlatformAnalysis
from app.geo_monitoring.services.projects import require_active_project
from app.geo_monitoring.services.runs import get_run

_RUN_TERMINAL = frozenset({"completed", "partial_success", "failed", "cancelled"})
_ANALYZED = frozenset({"completed", "partial_success"})


def _decimal_str(value: Decimal | None) -> str:
    if value is None:
        return "0"
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


def _aggregate_metric_snapshots(
    snapshots: list[MetricSnapshot],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, int]] = {}
    for row in snapshots:
        if row.prompt_id is not None:
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
        "data_completeness_rate": _decimal_str(
            completeness.quantize(Decimal("0.0001"))
        ),
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
