"""高频评价标签聚类：规则 / LLM / auto 策略与 run 级缓存。"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.sync_async import run_coroutine_sync
from app.core.exceptions import BusinessException
from app.geo_monitoring.agents.llm import (
    AgentLLMClient,
    AgentLLMConfig,
    AgentLLMFailure,
    AgentLLMRequest,
    AgentLLMResult,
    create_agent_llm_client,
)
from app.geo_monitoring.agents.schemas import EvaluationTagsLLMOutput
from app.geo_monitoring.analysis.metrics import compute_rate, normalize_metric_text
from app.geo_monitoring.models import Answer, MonitorRun, Prompt
from app.geo_monitoring.schemas import (
    EvaluationTagClusterMethod,
    EvaluationTagItemOut,
    EvaluationTagsOut,
)
from app.geo_monitoring.services.conversations import (
    _answer_filter_conditions,
    _answers_base_query,
    _normalize_platform_codes,
    _resolve_run,
)
from app.geo_monitoring.services.analysis import build_agent_llm_config
from app.geo_monitoring.services.projects import require_active_project

logger = logging.getLogger(__name__)

ClusterMethodParam = Literal["rule", "llm", "auto"]
EffectiveClusterMethod = Literal["rule", "llm"]

_RATE_QUANT = Decimal("0.0001")
_CACHE_ROOT_KEY = "evaluation_tags_cache"

_EVALUATION_TAG_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("演出质量", ("演出", "表演", "精彩", "震撼", "质量", "舞台")),
    ("性价比", ("性价比", "价格", "票价", "值得", "划算")),
    ("交通便利", ("交通", "方便", "地铁", "停车", "可达")),
    ("适合家庭", ("家庭", "亲子", "全家", "儿童", "老人")),
    ("沉浸体验", ("沉浸", "体验", "互动", "代入")),
    ("视觉效果", ("视觉", "灯光", "特效", "画面", "场景")),
    ("文化底蕴", ("文化", "历史", "底蕴", "传统", "故事")),
    ("排队体验", ("排队", "拥挤", "等待", "人流")),
)


def _decimal_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(_RATE_QUANT))


def _normalize_cluster_method(value: str | EvaluationTagClusterMethod) -> ClusterMethodParam:
    normalized = str(value).strip().lower()
    if normalized not in {
        EvaluationTagClusterMethod.RULE,
        EvaluationTagClusterMethod.LLM,
        EvaluationTagClusterMethod.AUTO,
    }:
        raise BusinessException(
            code=42200,
            message="cluster_method 必须是 rule、llm 或 auto",
            status_code=422,
        )
    return normalized  # type: ignore[return-value]


def _match_tags(text: str) -> set[str]:
    normalized = normalize_metric_text(text)
    if not normalized:
        return set()
    matched: set[str] = set()
    for tag, keywords in _EVALUATION_TAG_RULES:
        if any(keyword in normalized for keyword in keywords):
            matched.add(tag)
    return matched


def _load_prompt_answers(
    db: Session,
    *,
    run_id: int,
    prompt_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[Answer]:
    conditions = _answer_filter_conditions(
        run_id=run_id,
        prompt_id=prompt_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
    )
    return list(
        db.execute(
            _answers_base_query(conditions=conditions).order_by(Answer.id)
        )
        .scalars()
        .all()
    )


def _cluster_by_rule(
    answers: list[Answer], *, limit: int
) -> list[EvaluationTagItemOut]:
    tag_counts: dict[str, int] = {}
    for answer in answers:
        text = answer.normalized_text or answer.raw_text or ""
        for tag in _match_tags(text):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    answer_count = len(answers)
    rows = [
        EvaluationTagItemOut(
            tag=tag,
            count=count,
            share_rate=_decimal_str(compute_rate(count, answer_count)),
        )
        for tag, count in sorted(
            tag_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    if limit > 0:
        rows = rows[:limit]
    return rows


def _answer_fingerprint(answers: list[Answer]) -> str:
    if not answers:
        return "0"
    answer_ids = [answer.id for answer in answers]
    return f"{len(answer_ids)}:{min(answer_ids)}:{max(answer_ids)}"


def _cache_scope_key(
    *,
    prompt_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
    limit: int,
) -> str:
    payload = {
        "prompt_id": prompt_id,
        "platform_codes": sorted(platform_codes or []),
        "start_at": start_at.isoformat() if start_at else None,
        "end_at": end_at.isoformat() if end_at else None,
        "limit": limit,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return digest


def _load_cached_llm_payload(
    run: MonitorRun,
    *,
    cache_key: str,
    fingerprint: str,
) -> dict[str, Any] | None:
    cache_root = (run.result_json or {}).get(_CACHE_ROOT_KEY)
    if not isinstance(cache_root, dict):
        return None
    entry = cache_root.get(cache_key)
    if not isinstance(entry, dict):
        return None
    if entry.get("fingerprint") != fingerprint:
        return None
    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else None


def _save_cached_llm_payload(
    db: Session,
    run: MonitorRun,
    *,
    cache_key: str,
    fingerprint: str,
    payload: dict[str, Any],
) -> None:
    result_json = dict(run.result_json or {})
    cache_root = dict(result_json.get(_CACHE_ROOT_KEY) or {})
    cache_root[cache_key] = {
        "fingerprint": fingerprint,
        "payload": payload,
    }
    result_json[_CACHE_ROOT_KEY] = cache_root
    run.result_json = result_json
    db.flush()
    db.commit()


def _get_evaluation_tags_settings(settings: Settings | None = None) -> Settings:
    if settings is not None:
        return settings
    from app.core.config import get_settings

    return get_settings()


def _build_evaluation_tags_llm_client(
    settings: Settings | None = None,
    *,
    llm_client: AgentLLMClient | None = None,
) -> AgentLLMClient | None:
    if llm_client is not None:
        return llm_client
    cfg = _get_evaluation_tags_settings(settings)
    if not cfg.EVALUATION_TAGS_LLM_ENABLED:
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
        timeout_seconds=float(cfg.EVALUATION_TAGS_LLM_TIMEOUT_SECONDS),
        max_attempts=base_config.max_attempts,
        max_input_chars=cfg.EVALUATION_TAGS_LLM_MAX_INPUT_CHARS,
        temperature=base_config.temperature,
    )
    return create_agent_llm_client(generation_config)


def _truncate_answer_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return "..."[:max_chars]
    return text[: max_chars - 3] + "..."


def _format_answer_snippets(answers: list[Answer], *, max_answers: int) -> str:
    per_answer_limit = 400
    lines: list[str] = []
    for index, answer in enumerate(answers[:max_answers]):
        text = (answer.normalized_text or answer.raw_text or "").strip()
        if not text:
            continue
        clipped = _truncate_answer_text(text, per_answer_limit)
        lines.append(f"[{index}] {clipped}")
    return "\n".join(lines) if lines else "（无有效回答文本）"


def _items_from_llm_output(
    parsed: EvaluationTagsLLMOutput,
    *,
    answer_count: int,
    limit: int,
) -> list[EvaluationTagItemOut]:
    rows: list[EvaluationTagItemOut] = []
    for item in parsed.items:
        tag = item.tag.strip()
        if not tag:
            continue
        valid_indexes = sorted(
            {
                index
                for index in item.answer_indexes
                if isinstance(index, int) and 0 <= index < answer_count
            }
        )
        count = len(valid_indexes)
        if count <= 0:
            continue
        rows.append(
            EvaluationTagItemOut(
                tag=tag,
                count=count,
                share_rate=_decimal_str(compute_rate(count, answer_count)),
            )
        )
    rows.sort(key=lambda row: (-row.count, row.tag))
    if limit > 0:
        rows = rows[:limit]
    return rows


async def _call_llm_cluster(
    *,
    client: AgentLLMClient,
    prompt_text: str,
    answers: list[Answer],
    limit: int,
    max_answers: int,
) -> AgentLLMResult | AgentLLMFailure:
    request = AgentLLMRequest(
        template_key="cluster_evaluation_tags",
        variables={
            "prompt_text": prompt_text,
            "answer_count": str(len(answers)),
            "limit": str(limit),
            "answer_snippets": _format_answer_snippets(
                answers, max_answers=max_answers
            ),
        },
        output_schema=EvaluationTagsLLMOutput,
        agent_code="cluster_evaluation_tags",
        request_id=f"eval-tags-{uuid.uuid4().hex[:12]}",
    )
    return await client.generate_structured(request)


def _cluster_by_llm(
    db: Session,
    *,
    run: MonitorRun,
    prompt: Prompt,
    answers: list[Answer],
    limit: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
    settings: Settings | None = None,
    llm_client: AgentLLMClient | None = None,
) -> tuple[list[EvaluationTagItemOut], EffectiveClusterMethod] | None:
    cfg = _get_evaluation_tags_settings(settings)
    fingerprint = _answer_fingerprint(answers)
    cache_key = _cache_scope_key(
        prompt_id=prompt.id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    )
    cached = _load_cached_llm_payload(run, cache_key=cache_key, fingerprint=fingerprint)
    if cached is not None:
        items = [
            EvaluationTagItemOut.model_validate(item)
            for item in cached.get("items", [])
        ]
        return items, "llm"

    client = _build_evaluation_tags_llm_client(settings, llm_client=llm_client)
    if client is None:
        return None

    try:
        result = run_coroutine_sync(
            _call_llm_cluster(
                client=client,
                prompt_text=prompt.prompt_text,
                answers=answers,
                limit=limit,
                max_answers=cfg.EVALUATION_TAGS_LLM_MAX_ANSWERS,
            )
        )
    except Exception as exc:
        logger.warning("evaluation tags llm transport failed: %s", exc)
        return None

    if isinstance(result, AgentLLMFailure):
        logger.warning(
            "evaluation tags llm failed error_code=%s message=%s",
            result.error_code,
            result.error_message,
        )
        return None

    items = _items_from_llm_output(
        result.parsed,  # type: ignore[arg-type]
        answer_count=len(answers),
        limit=limit,
    )
    if not items:
        return None

    payload = {
        "items": [item.model_dump(mode="json") for item in items],
        "cluster_method": "llm",
    }
    _save_cached_llm_payload(
        db,
        run,
        cache_key=cache_key,
        fingerprint=fingerprint,
        payload=payload,
    )
    return items, "llm"


def _should_try_llm(
    *,
    cluster_method: ClusterMethodParam,
    rule_items: list[EvaluationTagItemOut],
    answer_count: int,
    settings: Settings,
) -> bool:
    if cluster_method == "rule":
        return False
    if cluster_method == "llm":
        return True
    if not settings.EVALUATION_TAGS_LLM_ENABLED:
        return False
    if rule_items:
        return False
    return answer_count >= settings.EVALUATION_TAGS_LLM_MIN_ANSWERS


def _build_response(
    *,
    run_id: int | None,
    prompt_id: int,
    cluster_method: EffectiveClusterMethod,
    answer_count: int,
    items: list[EvaluationTagItemOut],
) -> dict[str, Any]:
    return EvaluationTagsOut(
        run_id=run_id,
        prompt_id=prompt_id,
        cluster_method=cluster_method,
        answer_count=answer_count,
        items=items,
        total=len(items),
    ).model_dump(mode="json")


def cluster_evaluation_tags(
    db: Session,
    project_id: int,
    prompt_id: int,
    *,
    run_id: int | None = None,
    platform_codes: list[str] | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int = 10,
    cluster_method: ClusterMethodParam | EvaluationTagClusterMethod = EvaluationTagClusterMethod.AUTO,
    settings: Settings | None = None,
    llm_client: AgentLLMClient | None = None,
) -> dict[str, Any]:
    """对指定问题下的回答做评价标签聚类。"""
    require_active_project(db, project_id)
    normalized_method = _normalize_cluster_method(cluster_method)
    cfg = _get_evaluation_tags_settings(settings)
    platform_codes = _normalize_platform_codes(platform_codes)
    run = _resolve_run(db, project_id, run_id=run_id)
    if run is None:
        return _build_response(
            run_id=None,
            prompt_id=prompt_id,
            cluster_method="rule",
            answer_count=0,
            items=[],
        )

    prompt = db.execute(
        select(Prompt).where(
            Prompt.id == prompt_id,
            Prompt.prompt_set_id == run.prompt_set_id,
            Prompt.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if prompt is None:
        raise BusinessException(code=40400, message="监测问题不存在")

    answers = _load_prompt_answers(
        db,
        run_id=run.id,
        prompt_id=prompt_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
    )
    answer_count = len(answers)
    rule_items = _cluster_by_rule(answers, limit=limit)

    if normalized_method == "rule" or not _should_try_llm(
        cluster_method=normalized_method,
        rule_items=rule_items,
        answer_count=answer_count,
        settings=cfg,
    ):
        return _build_response(
            run_id=run.id,
            prompt_id=prompt_id,
            cluster_method="rule",
            answer_count=answer_count,
            items=rule_items,
        )

    llm_result = _cluster_by_llm(
        db,
        run=run,
        prompt=prompt,
        answers=answers,
        limit=limit,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        settings=cfg,
        llm_client=llm_client,
    )
    if llm_result is not None:
        items, effective_method = llm_result
        return _build_response(
            run_id=run.id,
            prompt_id=prompt_id,
            cluster_method=effective_method,
            answer_count=answer_count,
            items=items,
        )

    return _build_response(
        run_id=run.id,
        prompt_id=prompt_id,
        cluster_method="rule",
        answer_count=answer_count,
        items=rule_items,
    )
