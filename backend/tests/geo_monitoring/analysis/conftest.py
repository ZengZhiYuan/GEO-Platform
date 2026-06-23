"""分析指标测试夹具。"""

from __future__ import annotations

import pytest

from app.geo_monitoring.analysis.dto import (
    AnswerInput,
    BrandMentionInput,
    CitationInput,
)

TARGET_BRAND_ID = 1
COMPETITOR_A_ID = 2
COMPETITOR_B_ID = 3


@pytest.fixture
def target_brand_id() -> int:
    return TARGET_BRAND_ID


@pytest.fixture
def competitor_ids() -> tuple[int, int]:
    return COMPETITOR_A_ID, COMPETITOR_B_ID


def make_answer(
    *,
    answer_id: int,
    prompt_id: int = 101,
    platform_code: str = "qwen",
    task_status: str = "success",
    normalized_text: str = "示例回答",
    brand_mentions: tuple[BrandMentionInput, ...] = (),
    citations: tuple[CitationInput, ...] = (),
    agent_recommendation: bool | None = None,
) -> AnswerInput:
    return AnswerInput(
        answer_id=answer_id,
        prompt_id=prompt_id,
        platform_code=platform_code,
        task_status=task_status,
        normalized_text=normalized_text,
        brand_mentions=brand_mentions,
        citations=citations,
        agent_recommendation=agent_recommendation,
    )


def mention(
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
        mention_count=mention_count if mentioned else 0,
        first_position=first_position if mentioned else None,
        sentiment=sentiment,
    )


def citation(
    citation_no: int,
    *,
    url: str | None = None,
    domain: str | None = None,
    title: str | None = None,
) -> CitationInput:
    return CitationInput(
        citation_no=citation_no,
        url=url,
        domain=domain,
        title=title,
    )
