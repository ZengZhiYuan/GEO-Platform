"""竞品与 Prompt 竞争力纯函数。"""

from __future__ import annotations

from decimal import Decimal

from app.geo_monitoring.analysis.dto import (
    AnswerInput,
    CompetitorRow,
    PromptCompetitivenessRow,
    RateMetric,
)
from app.geo_monitoring.analysis.metrics import compute_rate, filter_valid_answers

_RANK_SCORES = {
    1: Decimal("100"),
    2: Decimal("70"),
    3: Decimal("50"),
}


# 计算目标品牌与竞品之间的可见度差距
def compute_competitor_advantage_gap(
    target_visibility: Decimal | None,
    competitor_visibility: Decimal | None,
) -> Decimal | None:
    if target_visibility is None or competitor_visibility is None:
        return None
    return (target_visibility - competitor_visibility).quantize(Decimal("0.000001"))


# 计算指定品牌在有效回答中的可见度比率
def compute_brand_visibility_for_brand(
    answers: list[AnswerInput],
    brand_id: int,
) -> RateMetric:
    valid_answers = filter_valid_answers(answers)
    numerator = sum(
        1
        for answer in valid_answers
        if any(
            mention.brand_id == brand_id and mention.is_mentioned
            for mention in answer.brand_mentions
        )
    )
    denominator = len(valid_answers)
    return RateMetric(
        numerator=numerator,
        denominator=denominator,
        rate=compute_rate(numerator, denominator),
    )


# 汇总竞品可见度并返回 Top N 排行
def compute_top_competitors(
    answers: list[AnswerInput],
    *,
    competitor_brand_ids: tuple[int, ...],
    brand_names: dict[int, str],
    limit: int = 5,
) -> list[CompetitorRow]:
    rows: list[CompetitorRow] = []
    for brand_id in competitor_brand_ids:
        visibility = compute_brand_visibility_for_brand(answers, brand_id)
        rows.append(
            CompetitorRow(
                brand_id=brand_id,
                brand_name=brand_names.get(brand_id, str(brand_id)),
                mention_answer_count=visibility.numerator,
                visibility_rate=visibility.rate,
            )
        )
    rows.sort(key=lambda row: (-row.mention_answer_count, row.brand_id))
    return rows[:limit]


# 根据提及排名映射竞争力得分
def _score_for_rank(rank: int | None) -> Decimal | None:
    if rank is None:
        return None
    if rank in _RANK_SCORES:
        return _RANK_SCORES[rank]
    if rank >= 4:
        return Decimal("30")
    return None


# 根据提及排名生成竞争力位置标签
def _position_label(rank: int | None) -> str | None:
    if rank is None:
        return "not_mentioned"
    if rank == 1:
        return "leading"
    if rank == 2:
        return "strong"
    if rank == 3:
        return "moderate"
    return "trailing"


# 按 Prompt 与平台维度计算目标品牌的竞争力行
def compute_prompt_competitiveness_rows(
    answers: list[AnswerInput],
    *,
    target_brand_id: int,
    competitor_brand_ids: tuple[int, ...],
) -> list[PromptCompetitivenessRow]:
    valid_answers = filter_valid_answers(answers)
    grouped: dict[tuple[int, str], list[AnswerInput]] = {}
    for answer in valid_answers:
        key = (answer.prompt_id, answer.platform_code)
        grouped.setdefault(key, []).append(answer)

    rows: list[PromptCompetitivenessRow] = []
    for (prompt_id, platform_code), prompt_answers in sorted(grouped.items()):
        answer = prompt_answers[0]
        # 按首次出现位置排序并计算各品牌排名
        mentioned = [
            mention
            for mention in answer.brand_mentions
            if mention.is_mentioned and mention.first_position is not None
        ]
        mentioned.sort(key=lambda item: (item.first_position or 0, item.brand_id))
        rank_by_brand = {
            mention.brand_id: index + 1 for index, mention in enumerate(mentioned)
        }
        target_rank = rank_by_brand.get(target_brand_id)
        competitors_json = tuple(
            {
                "brand_id": brand_id,
                "rank": rank_by_brand.get(brand_id),
            }
            for brand_id in competitor_brand_ids
        )
        rows.append(
            PromptCompetitivenessRow(
                prompt_id=prompt_id,
                platform_code=platform_code,
                target_rank=target_rank,
                target_first=target_rank == 1 if target_rank is not None else None,
                competitiveness_score=_score_for_rank(target_rank),
                competitors_json=competitors_json,
                position_label=_position_label(target_rank),
            )
        )
    return rows
