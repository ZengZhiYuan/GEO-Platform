"""AI 生成辅助服务：优先 Agent LLM，失败或未配置时规则兜底。"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.sync_async import run_coroutine_sync
from app.geo_monitoring.agents.llm import (
    AgentLLMClient,
    AgentLLMConfig,
    AgentLLMFailure,
    AgentLLMRequest,
    AgentLLMResult,
    create_agent_llm_client,
)
from app.geo_monitoring.agents.schemas import (
    AiBrandWordsLLMOutput,
    AiCompetitorsLLMOutput,
    AiQuestionsLLMOutput,
)
from app.geo_monitoring.schemas import (
    AiBrandWordsGenerateIn,
    AiCompetitorsGenerateIn,
    AiGeneratedQuestionOut,
    AiQuestionsGenerateIn,
)
from app.geo_monitoring.services import projects as project_service
from app.geo_monitoring.services.analysis import build_agent_llm_config

logger = logging.getLogger(__name__)

GenerationMethod = Literal["llm", "rule_fallback"]

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


def _get_ai_generation_settings(settings: Settings | None = None) -> Settings:
    if settings is not None:
        return settings
    from app.core.config import get_settings

    return get_settings()


def _build_ai_generation_llm_client(
    settings: Settings | None = None,
    *,
    llm_client: AgentLLMClient | None = None,
) -> AgentLLMClient | None:
    if llm_client is not None:
        return llm_client
    cfg = _get_ai_generation_settings(settings)
    if not cfg.AI_GENERATION_LLM_ENABLED:
        return None
    try:
        base_config = build_agent_llm_config(cfg)
    except Exception:
        return None
    generation_config = AgentLLMConfig(
        base_url=base_config.base_url,
        api_key=base_config.api_key,
        model=base_config.model,
        provider=base_config.provider,
        timeout_seconds=float(cfg.AI_GENERATION_TIMEOUT_SECONDS),
        max_attempts=base_config.max_attempts,
        max_input_chars=cfg.AI_GENERATION_MAX_INPUT_CHARS,
        temperature=base_config.temperature,
    )
    return create_agent_llm_client(generation_config)


def _with_generation_method(
    data: dict[str, Any], method: GenerationMethod
) -> dict[str, Any]:
    return {**data, "generation_method": method}


def _run_async(coro):
    return run_coroutine_sync(coro)


def _format_keyword_list(values: list[str]) -> str:
    if not values:
        return "无"
    return "、".join(values)


async def _generate_structured(
    *,
    client: AgentLLMClient,
    template_key: str,
    variables: dict[str, Any],
    output_schema: type,
    agent_code: str,
) -> AgentLLMResult | AgentLLMFailure:
    request = AgentLLMRequest(
        template_key=template_key,
        variables=variables,
        output_schema=output_schema,
        agent_code=agent_code,
        request_id=f"ai-gen-{uuid.uuid4().hex[:12]}",
    )
    return await client.generate_structured(request)


def _log_llm_failure(template_key: str, failure: AgentLLMFailure) -> None:
    logger.warning(
        "ai generation llm failed template=%s error_code=%s message=%s",
        template_key,
        failure.error_code,
        failure.error_message,
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


def _generate_brand_words_by_rules(payload: AiBrandWordsGenerateIn) -> dict[str, Any]:
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


def _normalize_llm_brand_words(
    payload: AiBrandWordsGenerateIn, parsed: AiBrandWordsLLMOutput
) -> dict[str, Any] | None:
    brand_name = payload.brand_name.strip()
    words = _dedupe_words(parsed.brand_words, limit=payload.limit, ensure=brand_name)
    if not words:
        return None
    return {"brand_words": words}


def generate_brand_words(
    payload: AiBrandWordsGenerateIn,
    *,
    settings: Settings | None = None,
    llm_client: AgentLLMClient | None = None,
) -> dict[str, Any]:
    client = _build_ai_generation_llm_client(settings, llm_client=llm_client)
    if client is not None:
        try:
            result = _run_async(
                _generate_structured(
                    client=client,
                    template_key="generate_brand_words",
                    variables={
                        "brand_name": payload.brand_name.strip(),
                        "category": payload.category or "未知",
                        "official_domain": payload.official_domain or "未知",
                        "limit": str(payload.limit),
                    },
                    output_schema=AiBrandWordsLLMOutput,
                    agent_code="generate_brand_words",
                )
            )
        except Exception as exc:
            logger.warning(
                "ai generation llm transport failed template=generate_brand_words: %s",
                exc,
            )
        else:
            if isinstance(result, AgentLLMResult):
                normalized = _normalize_llm_brand_words(
                    payload, result.parsed  # type: ignore[arg-type]
                )
                if normalized is not None:
                    return _with_generation_method(normalized, "llm")
            elif isinstance(result, AgentLLMFailure):
                _log_llm_failure("generate_brand_words", result)

    return _with_generation_method(
        _generate_brand_words_by_rules(payload),
        "rule_fallback",
    )


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


def _generate_competitors_by_rules(payload: AiCompetitorsGenerateIn) -> dict[str, Any]:
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


def _normalize_llm_competitors(
    payload: AiCompetitorsGenerateIn, parsed: AiCompetitorsLLMOutput
) -> dict[str, Any] | None:
    brand_name = payload.brand_name.strip()
    competitors: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for item in parsed.competitors:
        normalized = _normalize_competitor(item.model_dump(mode="python"))
        name = normalized["brand_name"]
        if name in seen_names or _is_same_brand(name, brand_name):
            continue
        seen_names.add(name)
        competitors.append(normalized)
        if len(competitors) >= payload.limit:
            break
    if not competitors:
        return None
    return {"competitors": competitors}


def generate_competitors(
    payload: AiCompetitorsGenerateIn,
    *,
    settings: Settings | None = None,
    llm_client: AgentLLMClient | None = None,
) -> dict[str, Any]:
    client = _build_ai_generation_llm_client(settings, llm_client=llm_client)
    if client is not None:
        try:
            result = _run_async(
                _generate_structured(
                    client=client,
                    template_key="generate_competitors",
                    variables={
                        "brand_name": payload.brand_name.strip(),
                        "category": payload.category or "未知",
                        "region": payload.region or "未知",
                        "limit": str(payload.limit),
                    },
                    output_schema=AiCompetitorsLLMOutput,
                    agent_code="generate_competitors",
                )
            )
        except Exception as exc:
            logger.warning(
                "ai generation llm transport failed template=generate_competitors: %s",
                exc,
            )
        else:
            if isinstance(result, AgentLLMResult):
                normalized = _normalize_llm_competitors(
                    payload, result.parsed  # type: ignore[arg-type]
                )
                if normalized is not None:
                    return _with_generation_method(normalized, "llm")
            elif isinstance(result, AgentLLMFailure):
                _log_llm_failure("generate_competitors", result)

    return _with_generation_method(
        _generate_competitors_by_rules(payload),
        "rule_fallback",
    )


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


def _generate_questions_by_rules(payload: AiQuestionsGenerateIn) -> dict[str, Any]:
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


def _normalize_llm_questions(
    payload: AiQuestionsGenerateIn, parsed: AiQuestionsLLMOutput
) -> dict[str, Any] | None:
    questions: list[dict[str, Any]] = []
    for item in parsed.questions[: payload.limit]:
        questions.append(
            AiGeneratedQuestionOut(
                prompt_text=item.prompt_text.strip(),
                prompt_type=item.prompt_type,
                core_keyword=item.core_keyword,
            ).model_dump(mode="json")
        )
    if not questions:
        return None
    return {"questions": questions}


def generate_questions(
    payload: AiQuestionsGenerateIn,
    *,
    settings: Settings | None = None,
    llm_client: AgentLLMClient | None = None,
) -> dict[str, Any]:
    client = _build_ai_generation_llm_client(settings, llm_client=llm_client)
    if client is not None:
        try:
            result = _run_async(
                _generate_structured(
                    client=client,
                    template_key="generate_questions",
                    variables={
                        "brand_name": payload.brand_name.strip(),
                        "category": payload.category or "未知",
                        "region": payload.region or "未知",
                        "core_keywords": _format_keyword_list(payload.core_keywords),
                        "competitors": _format_keyword_list(payload.competitors),
                        "limit": str(payload.limit),
                    },
                    output_schema=AiQuestionsLLMOutput,
                    agent_code="generate_questions",
                )
            )
        except Exception as exc:
            logger.warning(
                "ai generation llm transport failed template=generate_questions: %s",
                exc,
            )
        else:
            if isinstance(result, AgentLLMResult):
                normalized = _normalize_llm_questions(
                    payload, result.parsed  # type: ignore[arg-type]
                )
                if normalized is not None:
                    return _with_generation_method(normalized, "llm")
            elif isinstance(result, AgentLLMFailure):
                _log_llm_failure("generate_questions", result)

    return _with_generation_method(
        _generate_questions_by_rules(payload),
        "rule_fallback",
    )


def generate_brand_words_for_project(
    db: Session,
    project_id: int,
    payload: AiBrandWordsGenerateIn,
    *,
    settings: Settings | None = None,
    llm_client: AgentLLMClient | None = None,
) -> dict[str, Any]:
    project_service.get_project(db, project_id)
    return generate_brand_words(payload, settings=settings, llm_client=llm_client)


def generate_competitors_for_project(
    db: Session,
    project_id: int,
    payload: AiCompetitorsGenerateIn,
    *,
    settings: Settings | None = None,
    llm_client: AgentLLMClient | None = None,
) -> dict[str, Any]:
    project_service.get_project(db, project_id)
    return generate_competitors(payload, settings=settings, llm_client=llm_client)


def generate_questions_for_project(
    db: Session,
    project_id: int,
    payload: AiQuestionsGenerateIn,
    *,
    settings: Settings | None = None,
    llm_client: AgentLLMClient | None = None,
) -> dict[str, Any]:
    project_service.get_project(db, project_id)
    return generate_questions(payload, settings=settings, llm_client=llm_client)
