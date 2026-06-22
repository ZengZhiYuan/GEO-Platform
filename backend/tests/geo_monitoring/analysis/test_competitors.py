"""竞品指标与 Prompt 竞争力测试。"""

from decimal import Decimal

import pytest

from app.geo_monitoring.analysis.competitors import (
    compute_brand_visibility_for_brand,
    compute_competitor_advantage_gap,
    compute_prompt_competitiveness_rows,
    compute_top_competitors,
)
from app.geo_monitoring.analysis.dto import BrandMentionInput
from tests.geo_monitoring.analysis.conftest import (
    COMPETITOR_A_ID,
    COMPETITOR_B_ID,
    TARGET_BRAND_ID,
    make_answer,
    mention,
)


def test_competitor_advantage_gap():
    assert compute_competitor_advantage_gap(Decimal("0.6"), Decimal("0.4")) == Decimal("0.2")
    assert compute_competitor_advantage_gap(Decimal("0.4"), Decimal("0.6")) == Decimal("-0.2")
    assert compute_competitor_advantage_gap(None, Decimal("0.4")) is None


def test_brand_visibility_for_competitor():
    answers = [
        make_answer(answer_id=1, brand_mentions=(mention(COMPETITOR_A_ID),)),
        make_answer(answer_id=2, brand_mentions=(mention(TARGET_BRAND_ID),)),
    ]
    result = compute_brand_visibility_for_brand(answers, COMPETITOR_A_ID)
    assert result.numerator == 1
    assert result.denominator == 2
    assert result.rate == Decimal("0.5")


def test_top_competitors_ranked_by_answer_coverage():
    answers = [
        make_answer(
            answer_id=1,
            brand_mentions=(mention(COMPETITOR_A_ID), mention(COMPETITOR_B_ID)),
        ),
        make_answer(answer_id=2, brand_mentions=(mention(COMPETITOR_A_ID),)),
        make_answer(answer_id=3, brand_mentions=()),
    ]

    rows = compute_top_competitors(
        answers,
        competitor_brand_ids=(COMPETITOR_B_ID, COMPETITOR_A_ID),
        brand_names={COMPETITOR_A_ID: "CompA", COMPETITOR_B_ID: "CompB"},
        limit=2,
    )
    assert [row.brand_id for row in rows] == [COMPETITOR_A_ID, COMPETITOR_B_ID]
    assert rows[0].mention_answer_count == 2
    assert rows[1].mention_answer_count == 1


@pytest.mark.parametrize(
    ("first_positions", "expected_target_rank"),
    [
        ({TARGET_BRAND_ID: 10, COMPETITOR_A_ID: 30}, 1),
        ({TARGET_BRAND_ID: 40, COMPETITOR_A_ID: 5}, 2),
    ],
)
def test_prompt_competitiveness_rank_by_first_position(first_positions, expected_target_rank):
    mentions = tuple(
        BrandMentionInput(
            brand_id=brand_id,
            is_mentioned=True,
            mention_count=1,
            first_position=position,
        )
        for brand_id, position in first_positions.items()
    )
    answers = [
        make_answer(
            answer_id=1,
            prompt_id=501,
            platform_code="qwen",
            brand_mentions=mentions,
        )
    ]

    rows = compute_prompt_competitiveness_rows(
        answers,
        target_brand_id=TARGET_BRAND_ID,
        competitor_brand_ids=(COMPETITOR_A_ID,),
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.prompt_id == 501
    assert row.platform_code == "qwen"
    assert row.target_rank == expected_target_rank
    assert row.target_first is (expected_target_rank == 1)
    assert row.competitiveness_score == (
        Decimal("100") if expected_target_rank == 1 else Decimal("70")
    )


def test_prompt_competitiveness_rows_are_idempotent():
    answers = [
        make_answer(
            answer_id=1,
            prompt_id=501,
            brand_mentions=(
                BrandMentionInput(
                    brand_id=TARGET_BRAND_ID,
                    is_mentioned=True,
                    mention_count=1,
                    first_position=1,
                ),
            ),
        )
    ]
    first = compute_prompt_competitiveness_rows(
        answers,
        target_brand_id=TARGET_BRAND_ID,
        competitor_brand_ids=(COMPETITOR_A_ID,),
    )
    second = compute_prompt_competitiveness_rows(
        answers,
        target_brand_id=TARGET_BRAND_ID,
        competitor_brand_ids=(COMPETITOR_A_ID,),
    )
    assert first == second
