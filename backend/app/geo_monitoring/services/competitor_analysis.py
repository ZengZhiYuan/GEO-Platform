"""竞品分析页面级聚合服务。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessException
from app.geo_monitoring.analysis.brands import BrandProfile, compute_brand_metrics_rows
from app.geo_monitoring.analysis.dto import AnswerInput, BrandMentionInput
from app.geo_monitoring.analysis.metrics import compute_brand_rank_rate, compute_rate
from app.geo_monitoring.models import Answer, Brand, MonitorRun, QueryTask
from app.geo_monitoring.services.analysis import PlatformAnalysis
from app.geo_monitoring.services.dashboard import _select_latest_run
from app.geo_monitoring.services.projects import require_active_project
from app.geo_monitoring.services.runs import get_run

_RATE_QUANT = Decimal("0.0001")
_RANK_QUANT = Decimal("0.1")


@dataclass
class _AggBrandRow:
    brand_id: int
    brand_name: str
    mention_count: int = 0
    mention_numerator: int = 0
    mention_denominator: int = 0
    rank_weighted_sum: Decimal = Decimal("0")
    rank_weight: int = 0
    share_of_voice: Decimal | None = None


def _decimal_str(value: Decimal | None, *, quant: Decimal = _RATE_QUANT) -> str | None:
    if value is None:
        return None
    return str(value.quantize(quant))


def _rate_str(numerator: int, denominator: int) -> str | None:
    return _decimal_str(compute_rate(numerator, denominator))


def _normalize_platform_codes(platform_codes: list[str] | None) -> list[str] | None:
    if not platform_codes:
        return None
    return list(dict.fromkeys(code.strip() for code in platform_codes if code.strip()))


def _resolve_run(
    db: Session,
    project_id: int,
    *,
    run_id: int | None,
) -> MonitorRun | None:
    if run_id is not None:
        run = get_run(db, run_id)
        if run.project_id != project_id:
            raise BusinessException(code=40400, message="监测运行不存在")
        return run
    return _select_latest_run(db, project_id)


def _load_target_brand(db: Session, project_id: int) -> Brand:
    target = db.execute(
        select(Brand).where(
            Brand.project_id == project_id,
            Brand.brand_type == "target",
            Brand.is_deleted.is_(False),
            Brand.status == "active",
        )
    ).scalar_one_or_none()
    if target is None:
        raise BusinessException(code=40400, message="目标品牌不存在")
    return target


def _load_competitor_brands(db: Session, project_id: int) -> list[Brand]:
    return list(
        db.execute(
            select(Brand).where(
                Brand.project_id == project_id,
                Brand.brand_type == "competitor",
                Brand.is_deleted.is_(False),
                Brand.status == "active",
            )
            .order_by(Brand.id)
        )
        .scalars()
        .all()
    )


def _load_platform_analyses(
    db: Session,
    *,
    run_id: int,
    platform_codes: list[str] | None,
) -> list[PlatformAnalysis]:
    conditions = [
        PlatformAnalysis.run_id == run_id,
        PlatformAnalysis.is_deleted.is_(False),
    ]
    if platform_codes:
        conditions.append(PlatformAnalysis.platform_code.in_(platform_codes))
    return list(
        db.execute(select(PlatformAnalysis).where(*conditions))
        .scalars()
        .all()
    )


def _merge_brand_metric_row(bucket: _AggBrandRow, row: dict[str, Any]) -> None:
    bucket.brand_name = row.get("brand_name") or bucket.brand_name
    bucket.mention_count += int(row.get("mention_count") or 0)
    mention_rate = row.get("mention_rate") or {}
    bucket.mention_numerator += int(mention_rate.get("numerator") or 0)
    bucket.mention_denominator += int(mention_rate.get("denominator") or 0)
    average_rank = row.get("average_mention_rank")
    conversation_count = int(row.get("mention_conversation_count") or 0)
    if average_rank is not None and conversation_count > 0:
        rank_value = Decimal(str(average_rank))
        bucket.rank_weighted_sum += rank_value * conversation_count
        bucket.rank_weight += conversation_count


def _merge_agg_rows(target: _AggBrandRow, source: _AggBrandRow) -> None:
    target.brand_name = source.brand_name or target.brand_name
    target.mention_count += source.mention_count
    target.mention_numerator += source.mention_numerator
    target.mention_denominator += source.mention_denominator
    if source.rank_weight > 0:
        target.rank_weighted_sum += source.rank_weighted_sum
        target.rank_weight += source.rank_weight


def _copy_agg_row(row: _AggBrandRow) -> _AggBrandRow:
    return _AggBrandRow(
        brand_id=row.brand_id,
        brand_name=row.brand_name,
        mention_count=row.mention_count,
        mention_numerator=row.mention_numerator,
        mention_denominator=row.mention_denominator,
        rank_weighted_sum=row.rank_weighted_sum,
        rank_weight=row.rank_weight,
    )


def _merge_into_buckets(
    buckets: dict[int, _AggBrandRow],
    row_buckets: dict[int, _AggBrandRow],
) -> None:
    for brand_id, row in row_buckets.items():
        if brand_id in buckets:
            _merge_agg_rows(buckets[brand_id], row)
        else:
            buckets[brand_id] = _copy_agg_row(row)


def _allowed_brand_ids(
    target_brand: Brand,
    competitor_brands: list[Brand],
) -> frozenset[int]:
    return frozenset({target_brand.id, *(brand.id for brand in competitor_brands)})


def _validate_time_range(
    start_at: datetime | None,
    end_at: datetime | None,
) -> None:
    if start_at is not None and end_at is not None and start_at > end_at:
        raise BusinessException(code=422, message="start_at 不能晚于 end_at")


def _aggregate_from_brand_metrics(
    analysis_rows: list[PlatformAnalysis],
    *,
    allowed_brand_ids: frozenset[int],
) -> dict[int, _AggBrandRow]:
    buckets: dict[int, _AggBrandRow] = {}
    for analysis_row in analysis_rows:
        metrics = ((analysis_row.summary_json or {}).get("metrics") or {})
        for row in metrics.get("brand_metrics") or []:
            brand_id = int(row["brand_id"])
            if brand_id not in allowed_brand_ids:
                continue
            bucket = buckets.setdefault(
                brand_id,
                _AggBrandRow(brand_id=brand_id, brand_name=str(row.get("brand_name") or "")),
            )
            _merge_brand_metric_row(bucket, row)
    return buckets


def _aggregate_from_top_competitors(
    analysis_rows: list[PlatformAnalysis],
    *,
    target_brand: Brand,
    allowed_brand_ids: frozenset[int],
) -> dict[int, _AggBrandRow]:
    buckets: dict[int, _AggBrandRow] = {}
    for analysis_row in analysis_rows:
        valid = int(analysis_row.valid_answer_count or 0)
        target_bucket = buckets.setdefault(
            target_brand.id,
            _AggBrandRow(
                brand_id=target_brand.id,
                brand_name=target_brand.brand_name,
            ),
        )
        target_bucket.mention_numerator += int(analysis_row.brand_mention_count or 0)
        target_bucket.mention_denominator += valid
        target_bucket.mention_count += int(analysis_row.brand_mention_count or 0)

        for row in analysis_row.top_competitors or []:
            brand_id = int(row["brand_id"])
            if brand_id not in allowed_brand_ids:
                continue
            bucket = buckets.setdefault(
                brand_id,
                _AggBrandRow(brand_id=brand_id, brand_name=str(row.get("brand_name") or "")),
            )
            mention_answers = int(row.get("mention_answer_count") or 0)
            bucket.mention_numerator += mention_answers
            bucket.mention_denominator += valid
            bucket.mention_count += mention_answers
    return buckets


def _aggregate_platform_analyses(
    analysis_rows: list[PlatformAnalysis],
    *,
    target_brand: Brand,
    allowed_brand_ids: frozenset[int],
) -> dict[int, _AggBrandRow]:
    buckets: dict[int, _AggBrandRow] = {}
    for analysis_row in analysis_rows:
        metrics = ((analysis_row.summary_json or {}).get("metrics") or {})
        brand_metrics = metrics.get("brand_metrics") or []
        if brand_metrics:
            row_buckets = _aggregate_from_brand_metrics(
                [analysis_row],
                allowed_brand_ids=allowed_brand_ids,
            )
        else:
            row_buckets = _aggregate_from_top_competitors(
                [analysis_row],
                target_brand=target_brand,
                allowed_brand_ids=allowed_brand_ids,
            )
        _merge_into_buckets(buckets, row_buckets)
    if buckets:
        _recompute_share_of_voice(buckets)
    return buckets


def _recompute_share_of_voice(buckets: dict[int, _AggBrandRow]) -> None:
    conversation_counts = {
        brand_id: bucket.mention_numerator for brand_id, bucket in buckets.items()
    }
    total = sum(conversation_counts.values())
    if total == 0:
        for bucket in buckets.values():
            bucket.share_of_voice = None
        return
    for brand_id, bucket in buckets.items():
        bucket.share_of_voice = compute_rate(conversation_counts[brand_id], total)


def _answer_filter_conditions(
    *,
    run_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[Any]:
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
    return conditions


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


def _load_answers(
    db: Session,
    *,
    run_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[Answer]:
    conditions = _answer_filter_conditions(
        run_id=run_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
    )
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


def _aggregate_from_answers(
    answers: list[Answer],
    *,
    brands: list[Brand],
) -> dict[int, _AggBrandRow]:
    profiles = tuple(
        BrandProfile(
            brand_id=brand.id,
            brand_name=brand.brand_name,
            category=brand.brand_type,
        )
        for brand in brands
    )
    answer_inputs = [_answer_input_from_row(answer) for answer in answers]
    rows = compute_brand_metrics_rows(answer_inputs, brands=profiles)
    buckets: dict[int, _AggBrandRow] = {}
    for row in rows:
        bucket = _AggBrandRow(
            brand_id=row.brand_id,
            brand_name=row.brand_name,
            mention_count=row.mention_count,
            mention_numerator=row.mention_rate.numerator,
            mention_denominator=row.mention_rate.denominator,
            share_of_voice=row.share_of_voice,
        )
        if row.average_mention_rank is not None and row.mention_conversation_count > 0:
            bucket.rank_weighted_sum = row.average_mention_rank * row.mention_conversation_count
            bucket.rank_weight = row.mention_conversation_count
        buckets[row.brand_id] = bucket
    return buckets


def _aggregate_top1_kpi(analysis_rows: list[PlatformAnalysis]) -> str | None:
    numerator = 0
    denominator = 0
    for row in analysis_rows:
        metrics = ((row.summary_json or {}).get("metrics") or {})
        top1 = metrics.get("brand_top1_mention_rate") or {}
        numerator += int(top1.get("numerator") or row.brand_first_count or 0)
        denominator += int(top1.get("denominator") or row.valid_answer_count or 0)
    return _rate_str(numerator, denominator)


def _compute_top1_rate_from_answers(
    answers: list[Answer],
    *,
    target_brand_id: int,
) -> str | None:
    answer_inputs = [_answer_input_from_row(answer) for answer in answers]
    metric = compute_brand_rank_rate(
        answer_inputs,
        target_brand_id=target_brand_id,
        max_rank=1,
    )
    return _rate_str(metric.numerator, metric.denominator)


def _board_payload(
    bucket: _AggBrandRow,
    *,
    target_brand_id: int,
) -> dict[str, Any]:
    average_rank = None
    if bucket.rank_weight > 0:
        average_rank = _decimal_str(
            bucket.rank_weighted_sum / Decimal(bucket.rank_weight),
            quant=_RANK_QUANT,
        )
    return {
        "brand_id": bucket.brand_id,
        "brand_name": bucket.brand_name,
        "mention_rate": _rate_str(bucket.mention_numerator, bucket.mention_denominator),
        "mention_count": bucket.mention_count,
        "average_rank": average_rank,
        "share_of_voice": _decimal_str(bucket.share_of_voice),
        "is_target": bucket.brand_id == target_brand_id,
    }


def _build_boards(
    buckets: dict[int, _AggBrandRow],
    *,
    target_brand_id: int,
) -> dict[str, list[dict[str, Any]]]:
    rows = [_board_payload(bucket, target_brand_id=target_brand_id) for bucket in buckets.values()]

    mention_rate_board = sorted(
        rows,
        key=lambda item: (
            -(Decimal(item["mention_rate"] or "0")),
            -item["mention_count"],
            item["brand_id"],
        ),
    )
    average_rank_board = sorted(
        [item for item in rows if item["average_rank"] is not None],
        key=lambda item: (
            Decimal(item["average_rank"] or "0"),
            -(Decimal(item["mention_rate"] or "0")),
            item["brand_id"],
        ),
    )
    mention_count_board = sorted(
        rows,
        key=lambda item: (-item["mention_count"], item["brand_id"]),
    )
    return {
        "mention_rate": mention_rate_board,
        "average_rank": average_rank_board,
        "mention_count": mention_count_board,
    }


def _empty_trends() -> dict[str, list[Any]]:
    return {
        "days": [],
        "mention_rate": [],
        "average_rank": [],
        "mention_count": [],
    }


def _empty_payload(
    *,
    run_id: int | None,
    brand_scope: str,
    target_brand: Brand,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "brand_scope": brand_scope,
        "target_brand": {
            "brand_id": target_brand.id,
            "brand_name": target_brand.brand_name,
        },
        "has_analysis_data": False,
        "kpis": {
            "mention_rate": None,
            "mention_count": 0,
            "average_rank": None,
            "top1_rate": None,
            "share_of_voice": None,
        },
        "boards": {
            "mention_rate": [],
            "average_rank": [],
            "mention_count": [],
        },
        "trends": _empty_trends(),
    }


def get_competitor_analysis(
    db: Session,
    project_id: int,
    *,
    run_id: int | None = None,
    platform_codes: list[str] | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    brand_scope: str = "top5",
) -> dict[str, Any]:
    """聚合竞品分析页 KPI、榜单与趋势契约。"""
    require_active_project(db, project_id)
    _validate_time_range(start_at, end_at)
    normalized_scope = brand_scope
    platform_codes = _normalize_platform_codes(platform_codes)
    target_brand = _load_target_brand(db, project_id)
    competitor_brands = _load_competitor_brands(db, project_id)
    scoped_brands = [target_brand, *competitor_brands]
    allowed_brand_ids = _allowed_brand_ids(target_brand, competitor_brands)

    run = _resolve_run(db, project_id, run_id=run_id)
    if run is None:
        payload = _empty_payload(
            run_id=None,
            brand_scope=normalized_scope,
            target_brand=target_brand,
        )
        return payload

    analysis_rows = _load_platform_analyses(
        db,
        run_id=run.id,
        platform_codes=platform_codes,
    )
    if not analysis_rows:
        return _empty_payload(
            run_id=run.id,
            brand_scope=normalized_scope,
            target_brand=target_brand,
        )

    use_answer_recompute = start_at is not None or end_at is not None
    buckets: dict[int, _AggBrandRow] = {}
    filtered_answers: list[Answer] | None = None

    if use_answer_recompute:
        filtered_answers = _load_answers(
            db,
            run_id=run.id,
            platform_codes=platform_codes,
            start_at=start_at,
            end_at=end_at,
        )
        if filtered_answers:
            buckets = _aggregate_from_answers(filtered_answers, brands=scoped_brands)
    else:
        buckets = _aggregate_platform_analyses(
            analysis_rows,
            target_brand=target_brand,
            allowed_brand_ids=allowed_brand_ids,
        )

    if not buckets:
        return _empty_payload(
            run_id=run.id,
            brand_scope=normalized_scope,
            target_brand=target_brand,
        )

    if target_brand.id not in buckets:
        buckets[target_brand.id] = _AggBrandRow(
            brand_id=target_brand.id,
            brand_name=target_brand.brand_name,
        )
        _recompute_share_of_voice(buckets)

    target_bucket = buckets[target_brand.id]
    target_row = _board_payload(target_bucket, target_brand_id=target_brand.id)
    boards = _build_boards(buckets, target_brand_id=target_brand.id)
    if use_answer_recompute:
        top1_rate = (
            _compute_top1_rate_from_answers(
                filtered_answers or [],
                target_brand_id=target_brand.id,
            )
            if filtered_answers
            else None
        )
    else:
        top1_rate = _aggregate_top1_kpi(analysis_rows) if analysis_rows else None

    return {
        "run_id": run.id,
        "brand_scope": normalized_scope,
        "target_brand": {
            "brand_id": target_brand.id,
            "brand_name": target_brand.brand_name,
        },
        "has_analysis_data": True,
        "kpis": {
            "mention_rate": target_row["mention_rate"],
            "mention_count": target_row["mention_count"],
            "average_rank": target_row["average_rank"],
            "top1_rate": top1_rate,
            "share_of_voice": target_row["share_of_voice"],
        },
        "boards": boards,
        "trends": _empty_trends(),
    }
