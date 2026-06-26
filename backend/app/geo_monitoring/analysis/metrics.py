"""确定性监测指标纯函数。"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.geo_monitoring.analysis.dto import (
    AnswerInput,
    BrandMentionInput,
    CitationInput,
    PlatformMetricsOutput,
    RateMetric,
    RecommendationMetric,
)

_RATE_QUANT = Decimal("0.000001")

_RECOMMENDATION_PATTERNS = (
    r"推荐\s*{term}",
    r"首选\s*{term}",
    r"强烈推荐\s*{term}",
    r"recommend(?:ed|s|ing)?\s+{term}",
    r"{term}\s+is\s+(?:highly\s+)?recommended",
)


def normalize_metric_text(text: str) -> str:
    """统一大小写与全半角，便于规则指标计算。"""
    normalized = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", normalized).strip()


# 判断单条回答是否为可用于指标计算的有效回答
def is_valid_answer(answer: AnswerInput) -> bool:
    if answer.task_status != "success":
        return False
    return bool(normalize_metric_text(answer.normalized_text))


# 过滤出所有有效回答
def filter_valid_answers(answers: list[AnswerInput]) -> list[AnswerInput]:
    return [answer for answer in answers if is_valid_answer(answer)]


# 计算比率（分子/分母），分母为零时返回 None
def compute_rate(numerator: int, denominator: int) -> Decimal | None:
    if denominator == 0:
        return None
    value = Decimal(numerator) / Decimal(denominator)
    return value.quantize(_RATE_QUANT, rounding=ROUND_HALF_UP)


# 判断指定品牌是否在该回答中被提及
def _brand_mentioned(answer: AnswerInput, brand_id: int) -> bool:
    for mention in answer.brand_mentions:
        if mention.brand_id == brand_id:
            return mention.is_mentioned
    return False


# 计算目标品牌在有效回答中的可见度（提及率）
def compute_brand_visibility(
    answers: list[AnswerInput],
    *,
    target_brand_id: int,
) -> RateMetric:
    valid_answers = filter_valid_answers(answers)
    numerator = sum(
        1 for answer in valid_answers if _brand_mentioned(answer, target_brand_id)
    )
    denominator = len(valid_answers)
    return RateMetric(
        numerator=numerator,
        denominator=denominator,
        rate=compute_rate(numerator, denominator),
    )


# 计算目标品牌在有效回答中的相对提及排名
def _brand_rank(answer: AnswerInput, brand_id: int) -> int | None:
    mentioned = [
        mention
        for mention in answer.brand_mentions
        if mention.is_mentioned and mention.first_position is not None
    ]
    mentioned.sort(key=lambda item: (item.first_position or 0, item.brand_id))
    for index, mention in enumerate(mentioned, start=1):
        if mention.brand_id == brand_id:
            return index
    return None


# 计算目标品牌出现在指定 Top N 排名内的有效回答占比
def compute_brand_rank_rate(
    answers: list[AnswerInput],
    *,
    target_brand_id: int,
    max_rank: int,
) -> RateMetric:
    valid_answers = filter_valid_answers(answers)
    numerator = sum(
        1
        for answer in valid_answers
        if (rank := _brand_rank(answer, target_brand_id)) is not None
        and rank <= max_rank
    )
    denominator = len(valid_answers)
    return RateMetric(
        numerator=numerator,
        denominator=denominator,
        rate=compute_rate(numerator, denominator),
    )


# 计算含有效引用的回答占比（引用率）
def compute_citation_rate(answers: list[AnswerInput]) -> RateMetric:
    from app.geo_monitoring.analysis.sources import is_valid_citation

    valid_answers = filter_valid_answers(answers)
    numerator = sum(
        1
        for answer in valid_answers
        if any(is_valid_citation(citation) for citation in answer.citations)
    )
    denominator = len(valid_answers)
    return RateMetric(
        numerator=numerator,
        denominator=denominator,
        rate=compute_rate(numerator, denominator),
    )


# 收集目标品牌名与别名，去重并规范化
def _recommendation_terms(
    target_brand_name: str,
    target_aliases: tuple[str, ...],
) -> tuple[str, ...]:
    terms = [target_brand_name, *target_aliases]
    seen: set[str] = set()
    ordered: list[str] = []
    for term in terms:
        normalized = normalize_metric_text(term)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return tuple(ordered)


# 用正则规则检测文本是否推荐目标品牌
def detect_rule_recommendation(
    text: str,
    *,
    target_brand_name: str,
    target_aliases: tuple[str, ...],
) -> bool:
    normalized = normalize_metric_text(text)
    if not normalized:
        return False
    for term in _recommendation_terms(target_brand_name, target_aliases):
        escaped = re.escape(term)
        for template in _RECOMMENDATION_PATTERNS:
            pattern = re.compile(template.format(term=escaped), re.IGNORECASE)
            if pattern.search(normalized):
                return True
    return False


# 计算推荐率（规则、Agent 与合并三种口径）
def compute_recommendation_rate(
    answers: list[AnswerInput],
    *,
    target_brand_id: int,
    target_brand_name: str,
    target_aliases: tuple[str, ...] = (),
) -> RecommendationMetric:
    valid_answers = filter_valid_answers(answers)
    denominator = len(valid_answers)

    rule_numerator = 0
    agent_numerator = 0
    combined_numerator = 0
    for answer in valid_answers:
        if not _brand_mentioned(answer, target_brand_id):
            continue
        rule_hit = detect_rule_recommendation(
            answer.normalized_text,
            target_brand_name=target_brand_name,
            target_aliases=target_aliases,
        )
        agent_hit = answer.agent_recommendation is True
        if rule_hit:
            rule_numerator += 1
        if agent_hit:
            agent_numerator += 1
        if rule_hit or agent_hit:
            combined_numerator += 1

    return RecommendationMetric(
        numerator=combined_numerator,
        denominator=denominator,
        rate=compute_rate(combined_numerator, denominator),
        rule_numerator=rule_numerator,
        rule_rate=compute_rate(rule_numerator, denominator),
        agent_numerator=agent_numerator,
        agent_rate=compute_rate(agent_numerator, denominator),
        combined_numerator=combined_numerator,
        combined_rate=compute_rate(combined_numerator, denominator),
    )


# 汇总单平台全部确定性指标为 PlatformMetricsOutput
def compute_target_extended_metrics(
    answers: list[AnswerInput],
    *,
    target_brand_id: int,
    brand_ids: tuple[int, ...],
) -> dict[str, Any]:
    from app.geo_monitoring.analysis.brands import (
        compute_average_mention_rank,
        compute_brand_mention_count,
        compute_sentiment_rates,
        compute_share_of_voice,
    )

    sentiment_rates = compute_sentiment_rates(answers, target_brand_id)
    sov_by_brand = compute_share_of_voice(answers, brand_ids=brand_ids)
    return {
        "average_mention_rank": compute_average_mention_rank(answers, target_brand_id),
        "share_of_voice": sov_by_brand.get(target_brand_id),
        "brand_mention_total_count": compute_brand_mention_count(
            answers,
            target_brand_id,
        ),
        "brand_top10_mention_rate": compute_brand_rank_rate(
            answers,
            target_brand_id=target_brand_id,
            max_rank=10,
        ),
        "positive_rate": sentiment_rates["positive_rate"],
        "neutral_rate": sentiment_rates["neutral_rate"],
        "negative_rate": sentiment_rates["negative_rate"],
    }


def _collect_brand_ids(
    answers: list[AnswerInput],
    *,
    seed_ids: tuple[int, ...],
) -> tuple[int, ...]:
    seen = set(seed_ids)
    for answer in filter_valid_answers(answers):
        for mention in answer.brand_mentions:
            if mention.is_mentioned:
                seen.add(mention.brand_id)
    return tuple(sorted(seen))


def compute_platform_metrics(
    answers: list[AnswerInput],
    *,
    platform_code: str,
    target_brand_id: int,
    target_brand_name: str,
    target_aliases: tuple[str, ...] = (),
    competitor_brand_ids: tuple[int, ...] = (),
    brand_names: dict[int, str] | None = None,
    official_domain: str | None = None,
    brands: tuple["BrandProfile", ...] | None = None,
) -> PlatformMetricsOutput:
    from app.geo_monitoring.analysis.brands import BrandProfile, compute_brand_metrics_rows
    from app.geo_monitoring.analysis.competitors import (
        compute_brand_visibility_for_brand,
        compute_competitor_advantage_gap,
        compute_prompt_competitiveness_rows,
        compute_top_competitors,
    )
    from app.geo_monitoring.analysis.sources import (
        compute_source_coverage,
        compute_source_stats,
    )

    scoped = [answer for answer in answers if answer.platform_code == platform_code]
    valid_answers = filter_valid_answers(scoped)
    # 逐项计算平台级核心指标
    brand_visibility = compute_brand_visibility(
        scoped,
        target_brand_id=target_brand_id,
    )
    brand_top1_mention_rate = compute_brand_rank_rate(
        scoped,
        target_brand_id=target_brand_id,
        max_rank=1,
    )
    brand_top3_mention_rate = compute_brand_rank_rate(
        scoped,
        target_brand_id=target_brand_id,
        max_rank=3,
    )
    brand_top10_mention_rate = compute_brand_rank_rate(
        scoped,
        target_brand_id=target_brand_id,
        max_rank=10,
    )
    citation_rate = compute_citation_rate(scoped)
    recommendation = compute_recommendation_rate(
        scoped,
        target_brand_id=target_brand_id,
        target_brand_name=target_brand_name,
        target_aliases=target_aliases,
    )
    source_coverage = compute_source_coverage(
        scoped,
        official_domain=official_domain or "",
    )
    competitor_visibility = (
        compute_brand_visibility_for_brand(scoped, competitor_brand_ids[0])
        if competitor_brand_ids
        else RateMetric(0, len(valid_answers), compute_rate(0, len(valid_answers)))
    )
    competitor_advantage_gap = compute_competitor_advantage_gap(
        brand_visibility.rate,
        competitor_visibility.rate,
    )
    names = brand_names or {}
    top_competitors = tuple(
        compute_top_competitors(
            scoped,
            competitor_brand_ids=competitor_brand_ids,
            brand_names=names,
        )
    )
    source_stats = tuple(compute_source_stats(scoped, platform_code=platform_code))
    prompt_rows = tuple(
        compute_prompt_competitiveness_rows(
            scoped,
            target_brand_id=target_brand_id,
            competitor_brand_ids=competitor_brand_ids,
        )
    )
    brand_metrics: tuple = ()
    if brands:
        brand_metrics = tuple(compute_brand_metrics_rows(scoped, brands=brands))
    brand_ids = _collect_brand_ids(
        scoped,
        seed_ids=(target_brand_id, *competitor_brand_ids),
    )
    extended = compute_target_extended_metrics(
        scoped,
        target_brand_id=target_brand_id,
        brand_ids=brand_ids,
    )
    return PlatformMetricsOutput(
        platform_code=platform_code,
        valid_answer_count=len(valid_answers),
        brand_visibility=brand_visibility,
        brand_top1_mention_rate=brand_top1_mention_rate,
        brand_top3_mention_rate=brand_top3_mention_rate,
        brand_top10_mention_rate=brand_top10_mention_rate,
        citation_rate=citation_rate,
        recommendation=recommendation,
        source_coverage=source_coverage,
        competitor_advantage_gap=competitor_advantage_gap,
        top_competitors=top_competitors,
        source_stats=source_stats,
        prompt_competitiveness_rows=prompt_rows,
        average_mention_rank=extended["average_mention_rank"],
        share_of_voice=extended["share_of_voice"],
        brand_mention_total_count=extended["brand_mention_total_count"],
        positive_rate=extended["positive_rate"],
        neutral_rate=extended["neutral_rate"],
        negative_rate=extended["negative_rate"],
        brand_metrics=brand_metrics,
    )
