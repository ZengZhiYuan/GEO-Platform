"""来源统计与覆盖测试。"""

from decimal import Decimal

import pytest

from app.geo_monitoring.analysis.sources import (
    compute_source_coverage,
    compute_source_stats,
    is_valid_citation,
    normalize_domain,
)
from tests.geo_monitoring.analysis.conftest import citation, make_answer


@pytest.mark.parametrize(
    ("domain", "url", "expected"),
    [
        ("Example.COM", None, True),
        (None, "https://news.example.com/a", True),
        (None, None, False),
        ("", "   ", False),
    ],
)
def test_is_valid_citation(domain, url, expected):
    item = citation(1, domain=domain, url=url)
    assert is_valid_citation(item) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Example.COM", "example.com"),
        ("WWW.Example.COM", "example.com"),
        ("  Example.COM  ", "example.com"),
        (None, None),
    ],
)
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


def test_source_coverage_counts_deduplicated_answers():
    answers = [
        make_answer(
            answer_id=1,
            citations=(
                citation(1, domain="official.example", url="https://official.example/a"),
                citation(2, domain="official.example", url="https://official.example/b"),
            ),
        ),
        make_answer(
            answer_id=2,
            citations=(citation(1, domain="other.example", url="https://other.example"),),
        ),
        make_answer(
            answer_id=3,
            citations=(citation(1, domain="Official.Example", url="https://Official.Example"),),
        ),
    ]

    result = compute_source_coverage(answers, official_domain="official.example")
    assert result.numerator == 2
    assert result.denominator == 3
    assert result.rate == Decimal("0.666667")


def test_source_stats_duplicate_citations_and_idempotent():
    answers = [
        make_answer(
            answer_id=1,
            citations=(
                citation(1, domain="news.example", url="https://news.example/a"),
                citation(2, domain="news.example", url="https://news.example/b"),
            ),
        ),
        make_answer(
            answer_id=2,
            citations=(citation(1, domain="news.example", url="https://news.example/c"),),
        ),
    ]

    first = compute_source_stats(answers, platform_code="qwen")
    second = compute_source_stats(answers, platform_code="qwen")
    assert first == second

    news = next(item for item in first if item.domain == "news.example")
    assert news.citation_count == 3
    assert news.answer_coverage_count == 2
    assert news.share_rate == Decimal("1")


def test_source_stats_zero_denominator_returns_null_share():
    result = compute_source_stats([], platform_code="qwen")
    assert result == []
