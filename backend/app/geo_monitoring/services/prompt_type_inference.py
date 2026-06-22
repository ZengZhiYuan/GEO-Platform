"""根据问题文本自动推断 prompt_type。"""

from __future__ import annotations

_COMPARISON_HINTS = ("对比", "比较", "vs", "VS", "哪个更好", "哪个好", "还是")
_RECOMMENDATION_HINTS = ("推荐", "有哪些", "哪个值得", "哪家好", "最好", "首选")


def infer_prompt_type(
    prompt_text: str,
    *,
    brand_name: str | None = None,
    core_keyword: str | None = None,
) -> str:
    text = prompt_text.strip()
    lowered = text.lower()

    if any(hint.lower() in lowered for hint in _COMPARISON_HINTS):
        return "comparison"
    if any(hint in text for hint in _RECOMMENDATION_HINTS):
        return "recommendation"
    if brand_name and brand_name in text:
        return "brand_visibility"
    if core_keyword and core_keyword in text:
        if any(hint in text for hint in _RECOMMENDATION_HINTS):
            return "recommendation"
        return "brand_visibility"
    return "generic"
