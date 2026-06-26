"""行业基准参照服务。"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import BusinessException
from app.geo_monitoring.schemas import (
    BenchmarkDetailOut,
    BenchmarkIndustryOut,
    BenchmarkListOut,
    BenchmarkMetricsOut,
    MarketPositionThresholdOut,
)

_SAMPLE_SOURCE = "static_config"

_MARKET_POSITION_THRESHOLDS = (
    MarketPositionThresholdOut(
        code="leading",
        label="行业领先",
        min_mention_rate="0.5000",
    ),
    MarketPositionThresholdOut(
        code="above_average",
        label="高于行业平均",
        min_mention_rate="0.4500",
    ),
    MarketPositionThresholdOut(
        code="average",
        label="接近行业平均",
        min_mention_rate="0.3500",
    ),
    MarketPositionThresholdOut(
        code="below_average",
        label="低于行业平均",
        min_mention_rate="0.0000",
    ),
)

_INDUSTRY_BENCHMARKS: dict[str, BenchmarkMetricsOut] = {
    "文旅演艺": BenchmarkMetricsOut(
        mention_rate="0.4500",
        mention_count=12,
        average_rank="3.2",
        top1_rate="0.1800",
        share_of_voice="0.2500",
    ),
    "通用": BenchmarkMetricsOut(
        mention_rate="0.3800",
        mention_count=10,
        average_rank="3.8",
        top1_rate="0.1500",
        share_of_voice="0.2000",
    ),
}


def _serialize_industry(industry: str, metrics: BenchmarkMetricsOut) -> BenchmarkIndustryOut:
    return BenchmarkIndustryOut(
        industry=industry,
        metrics=metrics,
        market_position_thresholds=list(_MARKET_POSITION_THRESHOLDS),
    )


def list_benchmarks() -> dict[str, Any]:
    """返回全部行业基准列表。"""
    return BenchmarkListOut(
        sample_source=_SAMPLE_SOURCE,
        industries=[
            _serialize_industry(industry, metrics)
            for industry, metrics in sorted(_INDUSTRY_BENCHMARKS.items())
        ],
    ).model_dump(mode="json")


def get_industry_benchmark(industry: str) -> dict[str, Any]:
    """按行业返回基准指标，供竞品参照卡使用。"""
    normalized = industry.strip()
    metrics = _INDUSTRY_BENCHMARKS.get(normalized)
    if metrics is None:
        raise BusinessException(code=40400, message="行业基准不存在")
    return BenchmarkDetailOut(
        sample_source=_SAMPLE_SOURCE,
        industry=normalized,
        metrics=metrics,
        market_position_thresholds=list(_MARKET_POSITION_THRESHOLDS),
    ).model_dump(mode="json")


def get_benchmarks(*, industry: str | None = None) -> dict[str, Any]:
    if industry:
        return get_industry_benchmark(industry)
    return list_benchmarks()
