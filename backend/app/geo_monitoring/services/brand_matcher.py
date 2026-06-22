"""品牌与别名提及规则匹配。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.geo_monitoring.models import Brand, BrandAlias


@dataclass(frozen=True)
class BrandMatchResult:
    brand_id: int
    is_mentioned: bool
    mention_count: int
    first_position: int | None
    context_json: dict


def normalize_answer_text(text: str) -> str:
    """将平台回答标准化为可用于规则分析的纯文本。"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def match_brands_in_text(
    text: str,
    brands: list[Brand],
    aliases_by_brand: dict[int, list[BrandAlias]],
) -> list[BrandMatchResult]:
    """对项目品牌及启用别名执行 exact / contains / context 规则匹配。"""
    normalized = normalize_answer_text(text)
    lowered = normalized.lower()
    results: list[BrandMatchResult] = []

    for brand in brands:
        patterns = _brand_patterns(brand, aliases_by_brand.get(brand.id, ()))
        positions: list[int] = []
        matched_terms: list[str] = []
        # 汇总各匹配模式命中的位置与术语
        for pattern in patterns:
            found = _find_matches(normalized, lowered, pattern)
            if found:
                matched_terms.append(pattern.term)
                positions.extend(found)
        positions.sort()
        mention_count = len(positions)
        results.append(
            BrandMatchResult(
                brand_id=brand.id,
                is_mentioned=mention_count > 0,
                mention_count=mention_count,
                first_position=positions[0] if positions else None,
                context_json={"matched_terms": matched_terms},
            )
        )
    return results


@dataclass(frozen=True)
class _MatchPattern:
    term: str
    match_mode: str
    context_keywords: tuple[str, ...]


# 构建品牌名与启用别名的匹配模式列表
def _brand_patterns(brand: Brand, aliases: list[BrandAlias]) -> list[_MatchPattern]:
    # 品牌名默认 contains 匹配，再叠加启用别名的规则
    patterns = [
        _MatchPattern(term=brand.brand_name, match_mode="contains", context_keywords=())
    ]
    for alias in aliases:
        if not alias.enabled:
            continue
        patterns.append(
            _MatchPattern(
                term=alias.alias_name,
                match_mode=alias.match_mode,
                context_keywords=tuple(alias.context_keywords or ()),
            )
        )
    return patterns


# 按 match_mode 在文本中查找匹配位置
def _find_matches(
    normalized: str,
    lowered: str,
    pattern: _MatchPattern,
) -> list[int]:
    term = pattern.term.strip()
    if not term:
        return []
    term_lower = term.lower()
    if pattern.match_mode == "exact":
        # 整词边界精确匹配
        regex = re.compile(rf"(?<!\w){re.escape(term_lower)}(?!\w)", re.IGNORECASE)
        return [match.start() for match in regex.finditer(normalized)]
    if pattern.match_mode == "context":
        # 需同时出现上下文关键词
        if term_lower not in lowered:
            return []
        if pattern.context_keywords and not any(
            keyword.lower() in lowered for keyword in pattern.context_keywords
        ):
            return []
        return _find_substring_positions(lowered, term_lower)
    # contains 模式：子串出现即算匹配
    return _find_substring_positions(lowered, term_lower)


# 枚举小写文本中 needle 的所有起始位置
def _find_substring_positions(haystack_lower: str, needle_lower: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        index = haystack_lower.find(needle_lower, start)
        if index < 0:
            break
        positions.append(index)
        start = index + max(len(needle_lower), 1)
    return positions
