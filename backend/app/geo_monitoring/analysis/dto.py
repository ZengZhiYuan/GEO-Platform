"""分析指标输入/输出 DTO。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BrandMentionInput:
    brand_id: int
    is_mentioned: bool
    mention_count: int = 0
    first_position: int | None = None
    sentiment: str | None = None


@dataclass(frozen=True)
class CitationInput:
    citation_no: int
    url: str | None = None
    domain: str | None = None
    title: str | None = None
    source_type: str | None = None


@dataclass(frozen=True)
class AnswerInput:
    answer_id: int
    prompt_id: int
    platform_code: str
    task_status: str
    normalized_text: str
    brand_mentions: tuple[BrandMentionInput, ...] = ()
    citations: tuple[CitationInput, ...] = ()
    agent_recommendation: bool | None = None


@dataclass(frozen=True)
class RateMetric:
    numerator: int
    denominator: int
    rate: Decimal | None


@dataclass(frozen=True)
class RecommendationMetric:
    numerator: int
    denominator: int
    rate: Decimal | None
    rule_numerator: int
    rule_rate: Decimal | None
    agent_numerator: int
    agent_rate: Decimal | None
    combined_numerator: int
    combined_rate: Decimal | None


@dataclass(frozen=True)
class SourceStatRow:
    platform_code: str
    domain: str
    citation_count: int
    answer_coverage_count: int
    share_rate: Decimal | None
    rank_no: int


@dataclass(frozen=True)
class CompetitorRow:
    brand_id: int
    brand_name: str
    mention_answer_count: int
    visibility_rate: Decimal | None


@dataclass(frozen=True)
class PromptCompetitivenessRow:
    prompt_id: int
    platform_code: str
    target_rank: int | None
    target_first: bool | None
    competitiveness_score: Decimal | None
    competitors_json: tuple[dict[str, object], ...]
    position_label: str | None


@dataclass(frozen=True)
class BrandMetricsRow:
    brand_id: int
    brand_name: str
    brand_category: str
    mention_count: int
    mention_conversation_count: int
    mention_rate: RateMetric
    mention_rate_percent: Decimal | None
    average_mention_rank: Decimal | None
    share_of_voice: Decimal | None
    positive_neutral_sentiment_percent: Decimal | None
    brand_score: Decimal | None
    include_in_avg_rank_display: bool


@dataclass(frozen=True)
class PlatformMetricsOutput:
    platform_code: str
    valid_answer_count: int
    brand_visibility: RateMetric
    brand_top1_mention_rate: RateMetric
    brand_top3_mention_rate: RateMetric
    brand_top10_mention_rate: RateMetric
    citation_rate: RateMetric
    recommendation: RecommendationMetric
    source_coverage: RateMetric
    competitor_advantage_gap: Decimal | None
    top_competitors: tuple[CompetitorRow, ...]
    source_stats: tuple[SourceStatRow, ...]
    prompt_competitiveness_rows: tuple[PromptCompetitivenessRow, ...]
    average_mention_rank: Decimal | None
    share_of_voice: Decimal | None
    brand_mention_total_count: int
    positive_rate: RateMetric
    neutral_rate: RateMetric
    negative_rate: RateMetric
    brand_metrics: tuple[BrandMetricsRow, ...] = ()
