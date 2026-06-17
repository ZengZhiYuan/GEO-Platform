"""品牌级指标测试。"""

from decimal import Decimal

import pytest

from app.geo_monitoring.analysis.brands import (
    BrandProfile,
    compute_average_mention_rank,
    compute_brand_mention_count,
    compute_brand_metrics_rows,
    compute_brand_score,
    compute_positive_neutral_sentiment,
    compute_share_of_voice,
)
from app.geo_monitoring.analysis.dto import BrandMentionInput
from tests.geo_monitoring.analysis.conftest import (
    COMPETITOR_A_ID,
    COMPETITOR_B_ID,
    TARGET_BRAND_ID,
    make_answer,
)


def _mention(
    brand_id: int,
    *,
    mentioned: bool = True,
    mention_count: int = 1,
    first_position: int | None = 0,
    sentiment: str | None = None,
) -> BrandMentionInput:
    return BrandMentionInput(
        brand_id=brand_id,
        is_mentioned=mentioned,
        mention_count=mention_count,
        first_position=first_position,
        sentiment=sentiment,
    )


def test_brand_mention_count_sums_all_occurrences():
    answers = [
        make_answer(
            answer_id=1,
            brand_mentions=(_mention(TARGET_BRAND_ID, mention_count=3),),
        ),
        make_answer(
            answer_id=2,
            brand_mentions=(_mention(TARGET_BRAND_ID, mention_count=2),),
        ),
        make_answer(
            answer_id=3,
            brand_mentions=(_mention(TARGET_BRAND_ID, mentioned=False, mention_count=0),),
        ),
    ]

    assert compute_brand_mention_count(answers, TARGET_BRAND_ID) == 5


def test_brand_mention_rate_is_percentage_of_valid_conversations():
    answers = [
        make_answer(answer_id=1, brand_mentions=(_mention(TARGET_BRAND_ID),)),
        make_answer(answer_id=2, brand_mentions=(_mention(COMPETITOR_A_ID),)),
        make_answer(answer_id=3, brand_mentions=()),
        make_answer(answer_id=4, task_status="failed", brand_mentions=(_mention(TARGET_BRAND_ID),)),
    ]
    rows = compute_brand_metrics_rows(
        answers,
        brands=(
            BrandProfile(TARGET_BRAND_ID, "Target", "target"),
            BrandProfile(COMPETITOR_A_ID, "CompA", "competitor"),
        ),
    )
    target = next(row for row in rows if row.brand_id == TARGET_BRAND_ID)
    assert target.mention_conversation_count == 1
    assert target.mention_rate.denominator == 3
    assert target.mention_rate_percent == Decimal("33.333300")


def test_average_mention_rank_uses_first_position_order():
    answers = [
        make_answer(
            answer_id=1,
            brand_mentions=(
                _mention(COMPETITOR_A_ID, first_position=5),
                _mention(TARGET_BRAND_ID, first_position=20),
            ),
        ),
        make_answer(
            answer_id=2,
            brand_mentions=(
                _mention(TARGET_BRAND_ID, first_position=1),
                _mention(COMPETITOR_A_ID, first_position=30),
            ),
        ),
    ]

    assert compute_average_mention_rank(answers, TARGET_BRAND_ID) == Decimal("1.5")


def test_share_of_voice_counts_each_conversation_once_per_brand():
    answers = [
        make_answer(
            answer_id=1,
            brand_mentions=(
                _mention(TARGET_BRAND_ID, mention_count=5),
                _mention(COMPETITOR_A_ID, mention_count=2),
            ),
        ),
        make_answer(
            answer_id=2,
            brand_mentions=(_mention(TARGET_BRAND_ID, mention_count=1),),
        ),
    ]

    sov = compute_share_of_voice(
        answers,
        brand_ids=(TARGET_BRAND_ID, COMPETITOR_A_ID),
    )
    assert sov[TARGET_BRAND_ID] == Decimal("0.666667")
    assert sov[COMPETITOR_A_ID] == Decimal("0.333333")


@pytest.mark.parametrize(
    ("sentiments", "expected_percent"),
    [
        (("positive", "neutral"), Decimal("100")),
        (("positive", "negative"), Decimal("50")),
        (("negative", "negative"), Decimal("0")),
    ],
)
def test_positive_neutral_sentiment_rate(sentiments, expected_percent):
    answers = [
        make_answer(
            answer_id=index + 1,
            brand_mentions=(
                _mention(TARGET_BRAND_ID, sentiment=sentiment),
            ),
        )
        for index, sentiment in enumerate(sentiments)
    ]

    result = compute_positive_neutral_sentiment(answers, TARGET_BRAND_ID)
    assert result.rate == expected_percent / Decimal("100")


def test_brand_score_combines_weighted_components():
    score = compute_brand_score(
        mention_rate_percent=Decimal("40"),
        mention_count=10,
        average_mention_rank=Decimal("2"),
        positive_neutral_sentiment_percent=Decimal("80"),
    )
    assert score == Decimal("36.900000")


def test_brand_metrics_rows_limits_avg_rank_display_to_top_brands():
    brands = tuple(
        BrandProfile(brand_id, f"Brand{brand_id}", "discovered")
        for brand_id in range(1, 24)
    )
    answers = [
        make_answer(
            answer_id=brand_id,
            brand_mentions=(_mention(brand_id, first_position=0),),
        )
        for brand_id in range(1, 24)
    ]

    rows = compute_brand_metrics_rows(
        answers,
        brands=brands,
        avg_rank_display_limit=20,
    )
    included = [row for row in rows if row.include_in_avg_rank_display]
    assert len(included) == 20
    assert all(row.average_mention_rank is not None for row in included)
    excluded = next(row for row in rows if row.brand_id == 23)
    assert excluded.include_in_avg_rank_display is False


def test_brand_metrics_rows_are_idempotent():
    brands = (
        BrandProfile(TARGET_BRAND_ID, "Target", "target"),
        BrandProfile(COMPETITOR_A_ID, "CompA", "competitor"),
        BrandProfile(COMPETITOR_B_ID, "CompB", "discovered"),
    )
    answers = [
        make_answer(
            answer_id=1,
            brand_mentions=(
                _mention(TARGET_BRAND_ID, mention_count=2, first_position=1, sentiment="positive"),
                _mention(COMPETITOR_A_ID, first_position=10),
            ),
        ),
        make_answer(
            answer_id=2,
            brand_mentions=(_mention(COMPETITOR_B_ID, first_position=0, sentiment="neutral"),),
        ),
    ]
    first = compute_brand_metrics_rows(answers, brands=brands)
    second = compute_brand_metrics_rows(answers, brands=brands)
    assert first == second
