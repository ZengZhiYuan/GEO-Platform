"""品牌级确定性指标纯函数。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.geo_monitoring.analysis.dto import AnswerInput, BrandMetricsRow, BrandMentionInput, RateMetric
from app.geo_monitoring.analysis.metrics import compute_rate, filter_valid_answers

_SCORE_QUANT = Decimal("0.000001")
_DEFAULT_AVG_RANK_DISPLAY_LIMIT = 20
_DEFAULT_RANK_SCALE = 20

_POSITIVE_SENTIMENTS = frozenset({"positive", "pos", "正面"})
_NEUTRAL_SENTIMENTS = frozenset({"neutral", "中性", "normal"})


@dataclass(frozen=True)
class BrandProfile:
    brand_id: int
    brand_name: str
    category: str


def _mention_for_brand(
    answer: AnswerInput,
    brand_id: int,
) -> BrandMentionInput | None:
    for mention in answer.brand_mentions:
        if mention.brand_id == brand_id:
            return mention
    return None


def _brand_mentioned_in_answer(answer: AnswerInput, brand_id: int) -> bool:
    mention = _mention_for_brand(answer, brand_id)
    return mention is not None and mention.is_mentioned


def _rank_in_answer(answer: AnswerInput, brand_id: int) -> int | None:
    mentioned = [
        mention
        for mention in answer.brand_mentions
        if mention.is_mentioned and mention.first_position is not None
    ]
    if not mentioned:
        return None
    mentioned.sort(key=lambda item: (item.first_position or 0, item.brand_id))
    rank_by_brand = {
        mention.brand_id: index + 1 for index, mention in enumerate(mentioned)
    }
    return rank_by_brand.get(brand_id)


def compute_brand_mention_count(
    answers: list[AnswerInput],
    brand_id: int,
) -> int:
    total = 0
    for answer in filter_valid_answers(answers):
        mention = _mention_for_brand(answer, brand_id)
        if mention is None or not mention.is_mentioned:
            continue
        total += max(mention.mention_count, 1)
    return total


def compute_brand_mention_rate(
    answers: list[AnswerInput],
    brand_id: int,
) -> RateMetric:
    valid_answers = filter_valid_answers(answers)
    numerator = sum(
        1 for answer in valid_answers if _brand_mentioned_in_answer(answer, brand_id)
    )
    denominator = len(valid_answers)
    return RateMetric(
        numerator=numerator,
        denominator=denominator,
        rate=compute_rate(numerator, denominator),
    )


def compute_average_mention_rank(
    answers: list[AnswerInput],
    brand_id: int,
) -> Decimal | None:
    ranks: list[int] = []
    for answer in filter_valid_answers(answers):
        rank = _rank_in_answer(answer, brand_id)
        if rank is not None:
            ranks.append(rank)
    if not ranks:
        return None
    value = Decimal(sum(ranks)) / Decimal(len(ranks))
    return value.quantize(_SCORE_QUANT, rounding=ROUND_HALF_UP)


def compute_share_of_voice(
    answers: list[AnswerInput],
    *,
    brand_ids: tuple[int, ...],
) -> dict[int, Decimal | None]:
    conversation_counts = {
        brand_id: compute_brand_mention_rate(answers, brand_id).numerator
        for brand_id in brand_ids
    }
    total = sum(conversation_counts.values())
    if total == 0:
        return dict.fromkeys(brand_ids, None)
    return {
        brand_id: compute_rate(conversation_counts[brand_id], total)
        for brand_id in brand_ids
    }


def _is_positive_or_neutral(sentiment: str | None) -> bool:
    if sentiment is None:
        return False
    normalized = sentiment.strip().lower()
    return normalized in _POSITIVE_SENTIMENTS or normalized in _NEUTRAL_SENTIMENTS


def compute_positive_neutral_sentiment(
    answers: list[AnswerInput],
    brand_id: int,
) -> RateMetric:
    valid_answers = filter_valid_answers(answers)
    mention_conversations = 0
    positive_neutral_conversations = 0
    for answer in valid_answers:
        mention = _mention_for_brand(answer, brand_id)
        if mention is None or not mention.is_mentioned:
            continue
        mention_conversations += 1
        if _is_positive_or_neutral(mention.sentiment):
            positive_neutral_conversations += 1
    return RateMetric(
        numerator=positive_neutral_conversations,
        denominator=mention_conversations,
        rate=compute_rate(positive_neutral_conversations, mention_conversations),
    )


def compute_brand_score(
    *,
    mention_rate_percent: Decimal | None,
    mention_count: int,
    average_mention_rank: Decimal | None,
    positive_neutral_sentiment_percent: Decimal | None,
    rank_scale: int = _DEFAULT_RANK_SCALE,
) -> Decimal | None:
    if mention_rate_percent is None:
        return None

    mention_rate_part = mention_rate_percent * Decimal("0.75")
    mention_count_part = Decimal(mention_count) * Decimal("0.1")
    if average_mention_rank is None:
        rank_part = Decimal("0")
    else:
        rank_part = (Decimal(rank_scale + 1) - average_mention_rank) * Decimal("0.1")
    sentiment_part = (positive_neutral_sentiment_percent or Decimal("0")) * Decimal(
        "0.05"
    )
    score = mention_rate_part + mention_count_part + rank_part + sentiment_part
    return score.quantize(_SCORE_QUANT, rounding=ROUND_HALF_UP)


def _to_percent(rate: Decimal | None) -> Decimal | None:
    if rate is None:
        return None
    return (rate * Decimal("100")).quantize(_SCORE_QUANT, rounding=ROUND_HALF_UP)


def compute_brand_metrics_rows(
    answers: list[AnswerInput],
    *,
    brands: tuple[BrandProfile, ...],
    avg_rank_display_limit: int = _DEFAULT_AVG_RANK_DISPLAY_LIMIT,
) -> list[BrandMetricsRow]:
    brand_ids = tuple(brand.brand_id for brand in brands)
    sov_by_brand = compute_share_of_voice(answers, brand_ids=brand_ids)
    mention_counts = {
        brand.brand_id: compute_brand_mention_count(answers, brand.brand_id)
        for brand in brands
    }

    rate_rows = [
        (
            brand,
            compute_brand_mention_rate(answers, brand.brand_id),
        )
        for brand in brands
    ]
    rate_rows.sort(
        key=lambda item: (
            -(item[1].rate or Decimal("0")),
            -item[1].numerator,
            item[0].brand_id,
        )
    )
    top_brand_ids = {
        brand.brand_id for brand, _ in rate_rows[:avg_rank_display_limit]
    }

    rows: list[BrandMetricsRow] = []
    for brand in brands:
        mention_rate = compute_brand_mention_rate(answers, brand.brand_id)
        mention_rate_percent = _to_percent(mention_rate.rate)
        average_rank = compute_average_mention_rank(answers, brand.brand_id)
        sentiment = compute_positive_neutral_sentiment(answers, brand.brand_id)
        sentiment_percent = _to_percent(sentiment.rate)
        mention_count = mention_counts[brand.brand_id]
        rows.append(
            BrandMetricsRow(
                brand_id=brand.brand_id,
                brand_name=brand.brand_name,
                brand_category=brand.category,
                mention_count=mention_count,
                mention_conversation_count=mention_rate.numerator,
                mention_rate=mention_rate,
                mention_rate_percent=mention_rate_percent,
                average_mention_rank=average_rank,
                share_of_voice=sov_by_brand.get(brand.brand_id),
                positive_neutral_sentiment_percent=sentiment_percent,
                brand_score=compute_brand_score(
                    mention_rate_percent=mention_rate_percent,
                    mention_count=mention_count,
                    average_mention_rank=average_rank,
                    positive_neutral_sentiment_percent=sentiment_percent,
                ),
                include_in_avg_rank_display=brand.brand_id in top_brand_ids,
            )
        )
    rows.sort(key=lambda row: (-(row.brand_score or Decimal("0")), row.brand_id))
    return rows
