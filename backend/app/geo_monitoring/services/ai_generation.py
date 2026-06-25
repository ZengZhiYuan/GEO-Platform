"""AI 生成辅助服务（MVP 确定性规则，后续可替换为 LLM）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.geo_monitoring.schemas import (
    AiBrandWordsGenerateIn,
    AiCompetitorsGenerateIn,
    AiGeneratedQuestionOut,
    AiQuestionsGenerateIn,
)
from app.geo_monitoring.services import projects as project_service

_BRAND_WORD_PRESETS: dict[str, list[str]] = {
    "杭州宋城": ["宋城千古情", "千古情", "宋城", "宋城演艺", "SEP"],
}

_CATEGORY_BRAND_EXTRAS: dict[str, list[str]] = {
    "文旅演艺": ["千古情", "实景演艺"],
}

_REGION_CATEGORY_COMPETITORS: dict[tuple[str, str], list[dict[str, Any]]] = {
    ("文旅演艺", "杭州"): [
        {
            "brand_name": "印象西湖",
            "competitor_words": ["印象西湖", "印象西湖演出", "印象西湖秀"],
            "official_domain": None,
        },
        {
            "brand_name": "只有河南·戏剧幻城",
            "competitor_words": ["只有河南", "戏剧幻城", "只有河南·戏剧幻城"],
            "official_domain": "https://www.onlyhenan.com",
        },
    ],
}

_CATEGORY_COMPETITORS: dict[str, list[dict[str, Any]]] = {
    "文旅演艺": [
        {
            "brand_name": "只有河南·戏剧幻城",
            "competitor_words": ["只有河南", "戏剧幻城", "只有河南·戏剧幻城"],
            "official_domain": "https://www.onlyhenan.com",
        },
        {
            "brand_name": "长隆国际大马戏",
            "competitor_words": ["长隆", "长隆大马戏", "长隆国际大马戏"],
            "official_domain": "https://www.chimelong.com",
        },
        {
            "brand_name": "印象刘三姐",
            "competitor_words": ["印象刘三姐", "刘三姐"],
            "official_domain": None,
        },
        {
            "brand_name": "又见平遥",
            "competitor_words": ["又见平遥", "平遥"],
            "official_domain": None,
        },
    ],
}

_GENERIC_COMPETITORS: list[dict[str, Any]] = [
    {
        "brand_name": "行业竞品A",
        "competitor_words": ["行业竞品A"],
        "official_domain": None,
    },
    {
        "brand_name": "行业竞品B",
        "competitor_words": ["行业竞品B"],
        "official_domain": None,
    },
    {
        "brand_name": "行业竞品C",
        "competitor_words": ["行业竞品C"],
        "official_domain": None,
    },
]

_QUESTION_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("brand_sentiment", "{brand}怎么样？"),
    ("brand_info", "介绍一下{brand}。"),
    ("category_sentiment", "{topic}口碑怎么样？"),
    ("competitor_comparison", "{brand}和{competitor}哪个更值得看？"),
    ("category_recommendation", "推荐国内有哪些值得看的{category}项目？"),
)


def _normalize_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _dedupe_words(words: list[str], *, limit: int, ensure: str | None = None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    if ensure:
        ensure = ensure.strip()
        if ensure:
            seen.add(ensure)
            result.append(ensure)
            if len(result) >= limit:
                return result
    for word in words:
        cleaned = word.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _extract_brand_fragments(brand_name: str) -> list[str]:
    fragments: list[str] = []
    if len(brand_name) > 2 and brand_name.endswith("宋城"):
        fragments.append("宋城")
    if "宋城" in brand_name and brand_name != "宋城":
        fragments.append("宋城")
    return fragments


def generate_brand_words(payload: AiBrandWordsGenerateIn) -> dict[str, Any]:
    brand_name = payload.brand_name.strip()
    candidates = [brand_name]
    candidates.extend(_BRAND_WORD_PRESETS.get(brand_name, []))
    candidates.extend(_extract_brand_fragments(brand_name))
    category = _normalize_key(payload.category)
    if category:
        candidates.extend(_CATEGORY_BRAND_EXTRAS.get(category, []))
    return {
        "brand_words": _dedupe_words(candidates, limit=payload.limit, ensure=brand_name),
    }


def _brand_identity_tokens(brand_name: str) -> set[str]:
    tokens = {brand_name.strip()}
    tokens.update(_BRAND_WORD_PRESETS.get(brand_name, []))
    tokens.update(_extract_brand_fragments(brand_name))
    return {token for token in tokens if token}


def _is_same_brand(candidate_name: str, brand_name: str) -> bool:
    left = candidate_name.strip()
    right = brand_name.strip()
    if left == right or left in right or right in left:
        return True
    return left in _brand_identity_tokens(right)


def _normalize_competitor(item: dict[str, Any]) -> dict[str, Any]:
    brand_name = item["brand_name"].strip()
    words = _dedupe_words(
        [brand_name, *item.get("competitor_words", [])],
        limit=max(len(item.get("competitor_words", [])) + 1, 5),
        ensure=brand_name,
    )
    return {
        "brand_name": brand_name,
        "competitor_words": words,
        "official_domain": item.get("official_domain"),
    }


def generate_competitors(payload: AiCompetitorsGenerateIn) -> dict[str, Any]:
    brand_name = payload.brand_name.strip()
    category = _normalize_key(payload.category)
    region = _normalize_key(payload.region)

    pool: list[dict[str, Any]] = []
    if category and region:
        pool.extend(_REGION_CATEGORY_COMPETITORS.get((category, region), []))
    if category:
        pool.extend(_CATEGORY_COMPETITORS.get(category, []))
    if not pool:
        pool = list(_GENERIC_COMPETITORS)

    competitors: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for item in pool:
        normalized = _normalize_competitor(item)
        name = normalized["brand_name"]
        if name in seen_names or _is_same_brand(name, brand_name):
            continue
        seen_names.add(name)
        competitors.append(normalized)
        if len(competitors) >= payload.limit:
            break
    return {"competitors": competitors}


def _resolve_topic(payload: AiQuestionsGenerateIn) -> str:
    if payload.core_keywords:
        return payload.core_keywords[0].strip()
    if payload.region:
        return payload.region.strip()
    if payload.category:
        return payload.category.strip()
    return "该品类"


def _resolve_category(payload: AiQuestionsGenerateIn) -> str:
    if payload.category:
        return payload.category.strip()
    if payload.core_keywords:
        return payload.core_keywords[0].strip()
    return "相关品类"


def _resolve_competitor(payload: AiQuestionsGenerateIn) -> str:
    if payload.competitors:
        return payload.competitors[0].strip()
    return "主要竞品"


def _resolve_core_keyword(payload: AiQuestionsGenerateIn, prompt_type: str) -> str | None:
    if payload.core_keywords:
        return payload.core_keywords[0].strip()
    if prompt_type in {"category_sentiment", "category_recommendation"} and payload.category:
        return payload.category.strip()
    return None


def generate_questions(payload: AiQuestionsGenerateIn) -> dict[str, Any]:
    brand_name = payload.brand_name.strip()
    topic = _resolve_topic(payload)
    category = _resolve_category(payload)
    competitor = _resolve_competitor(payload)

    questions: list[dict[str, Any]] = []
    for index in range(payload.limit):
        prompt_type, template = _QUESTION_TEMPLATES[index % len(_QUESTION_TEMPLATES)]
        prompt_text = template.format(
            brand=brand_name,
            topic=topic,
            category=category,
            competitor=competitor,
        )
        questions.append(
            AiGeneratedQuestionOut(
                prompt_text=prompt_text,
                prompt_type=prompt_type,
                core_keyword=_resolve_core_keyword(payload, prompt_type),
            ).model_dump(mode="json")
        )
    return {"questions": questions}


def generate_brand_words_for_project(
    db: Session, project_id: int, payload: AiBrandWordsGenerateIn
) -> dict[str, Any]:
    project_service.get_project(db, project_id)
    return generate_brand_words(payload)


def generate_competitors_for_project(
    db: Session, project_id: int, payload: AiCompetitorsGenerateIn
) -> dict[str, Any]:
    project_service.get_project(db, project_id)
    return generate_competitors(payload)


def generate_questions_for_project(
    db: Session, project_id: int, payload: AiQuestionsGenerateIn
) -> dict[str, Any]:
    project_service.get_project(db, project_id)
    return generate_questions(payload)
