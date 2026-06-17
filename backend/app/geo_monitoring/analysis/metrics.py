"""确定性监测指标纯函数。"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP

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


def is_valid_answer(answer: AnswerInput) -> bool:
    if answer.task_status != "success":
        return False
    return bool(normalize_metric_text(answer.normalized_text))


def filter_valid_answers(answers: list[AnswerInput]) -> list[AnswerInput]:
    return [answer for answer in answers if is_valid_answer(answer)]


def compute_rate(numerator: int, denominator: int) -> Decimal | None:
    if denominator == 0:
        return None
    value = Decimal(numerator) / Decimal(denominator)
    return value.quantize(_RATE_QUANT, rounding=ROUND_HALF_UP)


def _brand_mentioned(answer: AnswerInput, brand_id: int) -> bool:
    for mention in answer.brand_mentions:
        if mention.brand_id == brand_id:
            return mention.is_mentioned
    return False


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
    brand_visibility = compute_brand_visibility(
        scoped,
        target_brand_id=target_brand_id,
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
    return PlatformMetricsOutput(
        platform_code=platform_code,
        valid_answer_count=len(valid_answers),
        brand_visibility=brand_visibility,
        citation_rate=citation_rate,
        recommendation=recommendation,
        source_coverage=source_coverage,
        competitor_advantage_gap=competitor_advantage_gap,
        top_competitors=top_competitors,
        source_stats=source_stats,
        prompt_competitiveness_rows=prompt_rows,
        brand_metrics=brand_metrics,
    )
