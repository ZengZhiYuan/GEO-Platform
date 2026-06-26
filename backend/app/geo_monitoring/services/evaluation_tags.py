"""高频评价标签规则聚类服务。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.analysis.metrics import compute_rate, normalize_metric_text
from app.geo_monitoring.models import Answer, Prompt
from app.geo_monitoring.schemas import EvaluationTagItemOut, EvaluationTagsOut
from app.geo_monitoring.services.conversations import (
    _answer_filter_conditions,
    _answers_base_query,
    _normalize_platform_codes,
    _resolve_run,
)
from app.geo_monitoring.services.projects import require_active_project

_RATE_QUANT = Decimal("0.0001")
_CLUSTER_METHOD = "rule"

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
) -> dict[str, Any]:
    """对指定问题下的回答做规则聚类，返回高频评价标签。"""
    require_active_project(db, project_id)
    platform_codes = _normalize_platform_codes(platform_codes)
    run = _resolve_run(db, project_id, run_id=run_id)
    if run is None:
        return EvaluationTagsOut(
            run_id=None,
            prompt_id=prompt_id,
            cluster_method=_CLUSTER_METHOD,
            answer_count=0,
            items=[],
            total=0,
        ).model_dump(mode="json")

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

    return EvaluationTagsOut(
        run_id=run.id,
        prompt_id=prompt_id,
        cluster_method=_CLUSTER_METHOD,
        answer_count=answer_count,
        items=rows,
        total=len(rows),
    ).model_dump(mode="json")
