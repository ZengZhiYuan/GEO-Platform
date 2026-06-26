"""确定性核心指标测试。"""

from decimal import Decimal

import pytest

from app.geo_monitoring.analysis.metrics import (
    compute_brand_rank_rate,
    compute_brand_visibility,
    compute_citation_rate,
    compute_platform_metrics,
    compute_recommendation_rate,
    compute_target_extended_metrics,
    filter_valid_answers,
    is_valid_answer,
    normalize_metric_text,
)
from tests.geo_monitoring.analysis.conftest import (
    COMPETITOR_A_ID,
    TARGET_BRAND_ID,
    citation,
    make_answer,
    mention,
)


@pytest.mark.parametrize(
    ("task_status", "text", "expected"),
    [
        ("success", "有内容", True),
        ("success", "  \n\t  ", False),
        ("failed", "有内容", False),
        ("cancelled", "有内容", False),
        ("success", "", False),
    ],
)
def test_is_valid_answer(task_status, text, expected):
    answer = make_answer(
        answer_id=1,
        task_status=task_status,
        normalized_text=text,
    )
    assert is_valid_answer(answer) is expected


@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [
        (0, 0, None),
        (2, 4, Decimal("0.5")),
        (1, 3, Decimal("0.333333")),
    ],
)
def test_compute_brand_visibility_rate(numerator, denominator, expected):
    answers = [
        make_answer(
            answer_id=index,
            brand_mentions=(mention(TARGET_BRAND_ID, mentioned=index < numerator),),
        )
        for index in range(denominator)
    ]
    if denominator == 0:
        answers = []

    result = compute_brand_visibility(answers, target_brand_id=TARGET_BRAND_ID)
    assert result.numerator == numerator
    assert result.denominator == denominator
    if expected is None:
        assert result.rate is None
    else:
        assert result.rate == expected


def test_brand_visibility_uses_only_valid_answers():
    answers = [
        make_answer(
            answer_id=1,
            brand_mentions=(mention(TARGET_BRAND_ID),),
        ),
        make_answer(
            answer_id=2,
            task_status="failed",
            brand_mentions=(mention(TARGET_BRAND_ID),),
        ),
        make_answer(
            answer_id=3,
            normalized_text="   ",
            brand_mentions=(mention(TARGET_BRAND_ID),),
        ),
    ]

    result = compute_brand_visibility(answers, target_brand_id=TARGET_BRAND_ID)
    assert result.numerator == 1
    assert result.denominator == 1
    assert result.rate == Decimal("1")


def test_compute_brand_rank_rate_counts_top1_and_top3_valid_answers():
    answers = [
        make_answer(
            answer_id=1,
            brand_mentions=(
                mention(TARGET_BRAND_ID, first_position=0),
                mention(COMPETITOR_A_ID, first_position=12),
            ),
        ),
        make_answer(
            answer_id=2,
            brand_mentions=(
                mention(COMPETITOR_A_ID, first_position=0),
                mention(TARGET_BRAND_ID, first_position=8),
            ),
        ),
        make_answer(
            answer_id=3,
            brand_mentions=(
                mention(COMPETITOR_A_ID, first_position=0),
                mention(3, first_position=3),
                mention(TARGET_BRAND_ID, first_position=20),
            ),
        ),
        make_answer(
            answer_id=4,
            brand_mentions=(mention(COMPETITOR_A_ID, first_position=0),),
        ),
        make_answer(
            answer_id=5,
            task_status="failed",
            brand_mentions=(mention(TARGET_BRAND_ID, first_position=0),),
        ),
    ]

    top1 = compute_brand_rank_rate(
        answers,
        target_brand_id=TARGET_BRAND_ID,
        max_rank=1,
    )
    top3 = compute_brand_rank_rate(
        answers,
        target_brand_id=TARGET_BRAND_ID,
        max_rank=3,
    )

    assert top1.numerator == 1
    assert top1.denominator == 4
    assert top1.rate == Decimal("0.25")
    assert top3.numerator == 3
    assert top3.denominator == 4
    assert top3.rate == Decimal("0.75")


@pytest.mark.parametrize(
    ("citations", "expected_numerator"),
    [
        ((), 0),
        ((citation(1, url="https://example.com/a", domain="example.com"),), 1),
        (
            (
                citation(1, url="https://example.com/a", domain="example.com"),
                citation(2, url="https://example.com/b", domain="example.com"),
            ),
            1,
        ),
        ((citation(1, title="无链接"),), 0),
    ],
)
def test_compute_citation_rate(citations, expected_numerator):
    answers = [
        make_answer(answer_id=1, citations=citations),
        make_answer(answer_id=2, citations=()),
    ]

    result = compute_citation_rate(answers)
    assert result.numerator == expected_numerator
    assert result.denominator == 2
    assert result.rate == Decimal(str(expected_numerator / 2))


def test_citation_rate_zero_denominator_returns_null():
    result = compute_citation_rate([])
    assert result.numerator == 0
    assert result.denominator == 0
    assert result.rate is None


@pytest.mark.parametrize(
    ("text", "expected_rule"),
    [
        ("我推荐 ScenicBrand 作为首选", True),
        ("I recommend ScenicBrand for travel", True),
        ("ScenicBrand is mentioned but not preferred", False),
        ("推荐 COMPETITOR 更合适", False),
    ],
)
def test_recommendation_rate_rule_detection(text, expected_rule):
    answers = [
        make_answer(
            answer_id=1,
            normalized_text=text,
            brand_mentions=(mention(TARGET_BRAND_ID),),
        )
    ]

    result = compute_recommendation_rate(
        answers,
        target_brand_id=TARGET_BRAND_ID,
        target_brand_name="ScenicBrand",
        target_aliases=("Scenic",),
    )
    assert result.rule_numerator == (1 if expected_rule else 0)
    assert result.agent_numerator == 0
    assert result.combined_numerator == (1 if expected_rule else 0)


def test_recommendation_rate_keeps_rule_and_agent_sources_separate():
    answers = [
        make_answer(
            answer_id=1,
            normalized_text="plain mention of ScenicBrand",
            brand_mentions=(mention(TARGET_BRAND_ID),),
            agent_recommendation=True,
        ),
        make_answer(
            answer_id=2,
            normalized_text="我推荐 ScenicBrand",
            brand_mentions=(mention(TARGET_BRAND_ID),),
            agent_recommendation=False,
        ),
    ]

    result = compute_recommendation_rate(
        answers,
        target_brand_id=TARGET_BRAND_ID,
        target_brand_name="ScenicBrand",
        target_aliases=(),
    )
    assert result.rule_numerator == 1
    assert result.agent_numerator == 1
    assert result.combined_numerator == 2
    assert result.rule_rate == Decimal("0.5")
    assert result.agent_rate == Decimal("0.5")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ＳｃｅｎｉｃＢｒａｎｄ", "ScenicBrand"),
        ("推荐　ScenicBrand", "推荐 ScenicBrand"),
    ],
)
def test_normalize_metric_text_handles_fullwidth(raw, expected):
    assert normalize_metric_text(raw) == expected


def test_filter_valid_answers_is_stable():
    answers = [
        make_answer(answer_id=1),
        make_answer(answer_id=2, task_status="failed"),
    ]
    assert [item.answer_id for item in filter_valid_answers(answers)] == [1]


def test_compute_brand_rank_rate_top10_uses_relative_rank():
    answers = [
        make_answer(
            answer_id=1,
            brand_mentions=(
                mention(COMPETITOR_A_ID, first_position=0),
                mention(TARGET_BRAND_ID, first_position=15),
            ),
        ),
        make_answer(
            answer_id=2,
            brand_mentions=(mention(TARGET_BRAND_ID, first_position=0),),
        ),
        make_answer(
            answer_id=3,
            brand_mentions=(
                mention(COMPETITOR_A_ID, first_position=0),
                mention(3, first_position=1),
                mention(4, first_position=2),
                mention(5, first_position=3),
                mention(6, first_position=4),
                mention(7, first_position=5),
                mention(8, first_position=6),
                mention(9, first_position=7),
                mention(10, first_position=8),
                mention(11, first_position=9),
                mention(TARGET_BRAND_ID, first_position=10),
            ),
        ),
    ]

    top10 = compute_brand_rank_rate(
        answers,
        target_brand_id=TARGET_BRAND_ID,
        max_rank=10,
    )
    assert top10.numerator == 2
    assert top10.denominator == 3
    assert top10.rate == Decimal("0.666667")


def test_compute_target_extended_metrics_covers_empty_multi_brand_and_mentions():
    empty = compute_target_extended_metrics(
        [],
        target_brand_id=TARGET_BRAND_ID,
        brand_ids=(TARGET_BRAND_ID, COMPETITOR_A_ID),
    )
    assert empty["average_mention_rank"] is None
    assert empty["share_of_voice"] is None
    assert empty["brand_mention_total_count"] == 0
    assert empty["brand_top10_mention_rate"].rate is None
    assert empty["positive_rate"].rate is None

    answers = [
        make_answer(
            answer_id=1,
            brand_mentions=(
                mention(TARGET_BRAND_ID, mention_count=3, first_position=2, sentiment="positive"),
                mention(COMPETITOR_A_ID, first_position=0),
            ),
        ),
        make_answer(
            answer_id=2,
            brand_mentions=(
                mention(TARGET_BRAND_ID, mention_count=2, first_position=1, sentiment="neutral"),
                mention(COMPETITOR_A_ID, first_position=5),
            ),
        ),
        make_answer(
            answer_id=3,
            brand_mentions=(mention(COMPETITOR_A_ID, first_position=0),),
        ),
    ]
    extended = compute_target_extended_metrics(
        answers,
        target_brand_id=TARGET_BRAND_ID,
        brand_ids=(TARGET_BRAND_ID, COMPETITOR_A_ID),
    )
    assert extended["average_mention_rank"] == Decimal("1.5")
    assert extended["share_of_voice"] == Decimal("0.400000")
    assert extended["brand_mention_total_count"] == 5
    assert extended["brand_top10_mention_rate"].numerator == 2
    assert extended["brand_top10_mention_rate"].denominator == 3
    assert extended["positive_rate"].rate == Decimal("0.5")
    assert extended["neutral_rate"].rate == Decimal("0.5")
    assert extended["negative_rate"].rate == Decimal("0")


def test_compute_platform_metrics_is_idempotent():
    answers = [
        make_answer(
            answer_id=1,
            brand_mentions=(mention(TARGET_BRAND_ID), mention(COMPETITOR_A_ID)),
            citations=(citation(1, url="https://official.example", domain="official.example"),),
        ),
        make_answer(
            answer_id=2,
            prompt_id=102,
            brand_mentions=(mention(COMPETITOR_A_ID),),
            citations=(),
        ),
    ]
    first = compute_platform_metrics(
        answers,
        platform_code="qwen",
        target_brand_id=TARGET_BRAND_ID,
        target_brand_name="ScenicBrand",
        target_aliases=("Scenic",),
        competitor_brand_ids=(COMPETITOR_A_ID,),
        official_domain="official.example",
    )
    second = compute_platform_metrics(
        answers,
        platform_code="qwen",
        target_brand_id=TARGET_BRAND_ID,
        target_brand_name="ScenicBrand",
        target_aliases=("Scenic",),
        competitor_brand_ids=(COMPETITOR_A_ID,),
        official_domain="official.example",
    )
    assert first == second
    assert first.valid_answer_count == 2
    assert first.brand_visibility.numerator == 1
    assert first.brand_top1_mention_rate.numerator == 1
    assert first.brand_top3_mention_rate.numerator == 1
    assert first.citation_rate.numerator == 1
    assert first.competitor_advantage_gap == Decimal("-0.5")
    assert first.average_mention_rank == Decimal("1")
    assert first.share_of_voice == Decimal("0.333333")
    assert first.brand_mention_total_count == 1
    assert first.brand_top10_mention_rate.numerator == 1
    assert first.positive_rate.denominator == 1
