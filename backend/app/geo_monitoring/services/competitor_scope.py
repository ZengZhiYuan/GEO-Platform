"""竞品展示范围解析。"""

from __future__ import annotations

from typing import Any, Protocol


class _BrandLike(Protocol):
    id: int
    brand_type: str


class _MentionLike(Protocol):
    brand_id: int
    is_mentioned: bool


class _AnswerLike(Protocol):
    brand_results: list[Any]


def resolve_competitor_brand_ids(
    *,
    brands: list[_BrandLike],
    target_brand_id: int,
    answers: list[_AnswerLike],
) -> tuple[int, ...]:
    configured = [
        brand.id
        for brand in brands
        if brand.brand_type == "competitor" and brand.id != target_brand_id
    ]
    if configured:
        return tuple(sorted(configured))

    discovered: set[int] = set()
    for answer in answers:
        for mention in answer.brand_results:
            if (
                mention.brand_id != target_brand_id
                and getattr(mention, "is_mentioned", False)
            ):
                discovered.add(mention.brand_id)
    if discovered:
        return tuple(sorted(discovered))

    fallback = [
        brand.id
        for brand in brands
        if brand.brand_type in {"competitor", "candidate"}
        and brand.id != target_brand_id
    ]
    return tuple(sorted(fallback))
