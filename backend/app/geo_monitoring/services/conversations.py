"""AI 对话记录问题聚合服务。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessException
from app.geo_monitoring.analysis.dto import AnswerInput
from app.geo_monitoring.analysis.metrics import compute_rate, is_valid_answer
from app.geo_monitoring.models import (
    Answer,
    Brand,
    MonitorRun,
    Prompt,
    QueryTask,
)
from app.geo_monitoring.services.dashboard import _select_latest_run
from app.geo_monitoring.services.projects import require_active_project
from app.geo_monitoring.services.runs import get_run

_RATE_QUANT = Decimal("0.0001")
_RANK_QUANT = Decimal("0.1")
_SENTIMENT_LABELS = ("positive", "neutral", "negative")


def _decimal_str(value: Decimal | None, *, quant: Decimal = _RATE_QUANT) -> str | None:
    if value is None:
        return None
    return str(value.quantize(quant))


def _rate_str(numerator: int, denominator: int) -> str | None:
    return _decimal_str(compute_rate(numerator, denominator))


def _normalize_platform_codes(platform_codes: list[str] | None) -> list[str] | None:
    if not platform_codes:
        return None
    return list(dict.fromkeys(code.strip() for code in platform_codes if code.strip()))


def _resolve_run(
    db: Session,
    project_id: int,
    *,
    run_id: int | None,
) -> MonitorRun | None:
    if run_id is not None:
        run = get_run(db, run_id)
        if run.project_id != project_id:
            raise BusinessException(code=40400, message="监测运行不存在")
        return run
    return _select_latest_run(db, project_id)


def _load_target_brand(db: Session, project_id: int) -> Brand:
    target = db.execute(
        select(Brand).where(
            Brand.project_id == project_id,
            Brand.brand_type == "target",
            Brand.is_deleted.is_(False),
            Brand.status == "active",
        )
    ).scalar_one_or_none()
    if target is None:
        raise BusinessException(code=40400, message="目标品牌不存在")
    return target


def _answer_filter_conditions(
    *,
    run_id: int,
    prompt_id: int | None = None,
    prompt_ids: list[int] | None = None,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[Any]:
    conditions: list[Any] = [
        QueryTask.run_id == run_id,
        QueryTask.is_deleted.is_(False),
        Answer.is_deleted.is_(False),
    ]
    if prompt_id is not None:
        conditions.append(Answer.prompt_id == prompt_id)
    elif prompt_ids:
        conditions.append(Answer.prompt_id.in_(prompt_ids))
    if platform_codes:
        conditions.append(Answer.platform_code.in_(platform_codes))
    if start_at is not None:
        conditions.append(Answer.collected_at >= start_at)
    if end_at is not None:
        conditions.append(Answer.collected_at <= end_at)
    return conditions


def _answers_base_query(*, conditions: list[Any]):
    return (
        select(Answer)
        .join(QueryTask, QueryTask.id == Answer.task_id)
        .where(*conditions)
    )


def _load_summary_answers(
    db: Session,
    *,
    run_id: int,
    prompt_ids: list[int],
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[Answer]:
    if not prompt_ids:
        return []
    conditions = _answer_filter_conditions(
        run_id=run_id,
        prompt_ids=prompt_ids,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
    )
    return list(
        db.execute(
            _answers_base_query(conditions=conditions)
            .options(
                selectinload(Answer.brand_results),
                selectinload(Answer.task),
            )
            .order_by(Answer.prompt_id, Answer.platform_code, Answer.id)
        )
        .scalars()
        .all()
    )


def _count_prompt_answers(
    db: Session,
    *,
    run_id: int,
    prompt_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> int:
    conditions = _answer_filter_conditions(
        run_id=run_id,
        prompt_id=prompt_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
    )
    return (
        db.scalar(
            select(func.count())
            .select_from(Answer)
            .join(QueryTask, QueryTask.id == Answer.task_id)
            .where(*conditions)
        )
        or 0
    )


def _load_prompt_answers_page(
    db: Session,
    *,
    run_id: int,
    prompt_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
    page: int,
    page_size: int,
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
            _answers_base_query(conditions=conditions)
            .options(
                selectinload(Answer.citations),
                selectinload(Answer.brand_results),
            )
            .order_by(Answer.platform_code, Answer.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )


def _prompts_with_answers_query(
    *,
    prompt_set_id: int,
    run_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
    keyword: str | None,
):
    conditions = _answer_filter_conditions(
        run_id=run_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
    )
    stmt = (
        select(Prompt)
        .join(Answer, Answer.prompt_id == Prompt.id)
        .join(QueryTask, QueryTask.id == Answer.task_id)
        .where(
            Prompt.prompt_set_id == prompt_set_id,
            Prompt.is_deleted.is_(False),
            *conditions,
        )
        .distinct()
    )
    if keyword and keyword.strip():
        stmt = stmt.where(Prompt.prompt_text.ilike(f"%{keyword.strip()}%"))
    return stmt


def _count_matching_prompts(
    db: Session,
    *,
    prompt_set_id: int,
    run_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
    keyword: str | None,
) -> int:
    stmt = _prompts_with_answers_query(
        prompt_set_id=prompt_set_id,
        run_id=run_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        keyword=keyword,
    )
    return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def _load_matching_prompts_page(
    db: Session,
    *,
    prompt_set_id: int,
    run_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> list[Prompt]:
    stmt = _prompts_with_answers_query(
        prompt_set_id=prompt_set_id,
        run_id=run_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        keyword=keyword,
    )
    return list(
        db.execute(
            stmt.order_by(Prompt.id).offset((page - 1) * page_size).limit(page_size)
        )
        .scalars()
        .all()
    )


def _target_brand_result(answer: Answer, target_brand_id: int):
    for result in answer.brand_results:
        if result.brand_id == target_brand_id:
            return result
    return None


def _is_answer_valid(answer: Answer) -> bool:
    task_status = answer.task.status if answer.task is not None else "failed"
    text = answer.normalized_text or answer.raw_text or ""
    return is_valid_answer(
        AnswerInput(
            answer_id=answer.id,
            prompt_id=answer.prompt_id,
            platform_code=answer.platform_code,
            task_status=task_status,
            normalized_text=text,
        )
    )


def _sentiment_summary(
    answers: list[Answer],
    *,
    target_brand_id: int,
) -> dict[str, int]:
    counts = {label: 0 for label in _SENTIMENT_LABELS}
    for answer in answers:
        if not _is_answer_valid(answer):
            continue
        result = _target_brand_result(answer, target_brand_id)
        if result is None or not result.is_mentioned:
            continue
        label = (result.sentiment or "neutral").lower()
        if label not in counts:
            label = "neutral"
        counts[label] += 1
    return counts


def _compute_metrics(
    answers: list[Answer],
    *,
    target_brand_id: int,
) -> dict[str, Any]:
    valid_answers = [answer for answer in answers if _is_answer_valid(answer)]
    denominator = len(valid_answers)
    mention_answers = [
        answer
        for answer in valid_answers
        if (result := _target_brand_result(answer, target_brand_id)) is not None
        and result.is_mentioned
    ]
    mention_count = sum(
        (_target_brand_result(answer, target_brand_id).mention_count or 0)
        for answer in mention_answers
        if _target_brand_result(answer, target_brand_id) is not None
    )
    top1_count = sum(
        1
        for answer in mention_answers
        if (result := _target_brand_result(answer, target_brand_id)) is not None
        and result.first_position is not None
        and result.first_position <= 1
    )
    top3_count = sum(
        1
        for answer in mention_answers
        if (result := _target_brand_result(answer, target_brand_id)) is not None
        and result.first_position is not None
        and result.first_position <= 3
    )
    rank_positions = [
        result.first_position
        for answer in mention_answers
        if (result := _target_brand_result(answer, target_brand_id)) is not None
        and result.first_position is not None
    ]
    average_rank = None
    if rank_positions:
        average_rank = _decimal_str(
            Decimal(sum(rank_positions)) / Decimal(len(rank_positions)),
            quant=_RANK_QUANT,
        )

    return {
        "valid_answer_count": denominator,
        "visibility_rate": _rate_str(len(mention_answers), denominator),
        "mention_count": mention_count,
        "average_rank": average_rank,
        "top1_rate": _rate_str(top1_count, denominator),
        "top3_rate": _rate_str(top3_count, denominator),
        "sentiment": _sentiment_summary(valid_answers, target_brand_id=target_brand_id),
    }


def _build_platform_metrics(
    answers: list[Answer],
    *,
    target_brand_id: int,
    platform_codes: list[str] | None,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Answer]] = defaultdict(list)
    for answer in answers:
        grouped[answer.platform_code].append(answer)

    ordered_codes = platform_codes or sorted(grouped)
    metrics: list[dict[str, Any]] = []
    for code in ordered_codes:
        platform_answers = grouped.get(code, [])
        if not platform_answers:
            continue
        payload = _compute_metrics(platform_answers, target_brand_id=target_brand_id)
        metrics.append({"platform_code": code, **payload})
    return metrics


def _build_question_row(
    *,
    prompt: Prompt,
    run_id: int,
    answers: list[Answer],
    target_brand_id: int,
    platform_codes: list[str] | None,
) -> dict[str, Any]:
    summary = _compute_metrics(answers, target_brand_id=target_brand_id)
    return {
        "prompt_id": prompt.id,
        "prompt_text": prompt.prompt_text,
        "prompt_type": prompt.prompt_type,
        "run_id": run_id,
        **summary,
        "platform_metrics": _build_platform_metrics(
            answers,
            target_brand_id=target_brand_id,
            platform_codes=platform_codes,
        ),
    }


def list_conversation_questions(
    db: Session,
    project_id: int,
    *,
    run_id: int | None = None,
    platform_codes: list[str] | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """按 prompt 聚合对话记录主表。"""
    require_active_project(db, project_id)
    platform_codes = _normalize_platform_codes(platform_codes)
    run = _resolve_run(db, project_id, run_id=run_id)
    if run is None:
        return {
            "run_id": None,
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
        }

    target = _load_target_brand(db, project_id)
    total = _count_matching_prompts(
        db,
        prompt_set_id=run.prompt_set_id,
        run_id=run.id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        keyword=keyword,
    )
    prompts = _load_matching_prompts_page(
        db,
        prompt_set_id=run.prompt_set_id,
        run_id=run.id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    if not prompts:
        return {
            "run_id": run.id,
            "items": [],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    answers = _load_summary_answers(
        db,
        run_id=run.id,
        prompt_ids=[prompt.id for prompt in prompts],
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
    )
    grouped: dict[int, list[Answer]] = defaultdict(list)
    for answer in answers:
        grouped[answer.prompt_id].append(answer)

    rows = [
        _build_question_row(
            prompt=prompt,
            run_id=run.id,
            answers=grouped.get(prompt.id, []),
            target_brand_id=target.id,
            platform_codes=platform_codes,
        )
        for prompt in prompts
    ]
    return {
        "run_id": run.id,
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _serialize_answer_detail(
    answer: Answer,
    *,
    prompt: Prompt,
    brand_names: dict[int, str],
) -> dict[str, Any]:
    return {
        "answer_id": answer.id,
        "platform_code": answer.platform_code,
        "prompt_id": answer.prompt_id,
        "prompt_text": prompt.prompt_text,
        "prompt_type": prompt.prompt_type,
        "raw_text": answer.raw_text,
        "normalized_text": answer.normalized_text,
        "collected_at": answer.collected_at.isoformat(),
        "reasoning_text": None,
        "search_keywords": [],
        "citations": [
            {
                "id": citation.id,
                "answer_id": citation.answer_id,
                "citation_no": citation.citation_no,
                "title": citation.title,
                "url": citation.url,
                "domain": citation.domain,
                "source_type": citation.source_type,
                "quoted_text": citation.quoted_text,
            }
            for citation in answer.citations
        ],
        "brand_results": [
            {
                "brand_id": result.brand_id,
                "brand_name": brand_names.get(result.brand_id, ""),
                "is_mentioned": result.is_mentioned,
                "mention_count": result.mention_count,
                "first_position": result.first_position,
                "sentiment": result.sentiment,
            }
            for result in answer.brand_results
            if result.is_mentioned
        ],
    }


def list_conversation_question_answers(
    db: Session,
    project_id: int,
    prompt_id: int,
    *,
    run_id: int | None = None,
    platform_codes: list[str] | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """返回指定问题下的各平台回答详情。"""
    require_active_project(db, project_id)
    platform_codes = _normalize_platform_codes(platform_codes)
    run = _resolve_run(db, project_id, run_id=run_id)
    if run is None:
        return {
            "run_id": None,
            "prompt_id": prompt_id,
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
        }

    prompt = db.execute(
        select(Prompt).where(
            Prompt.id == prompt_id,
            Prompt.prompt_set_id == run.prompt_set_id,
            Prompt.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if prompt is None:
        raise BusinessException(code=40400, message="监测问题不存在")

    total = _count_prompt_answers(
        db,
        run_id=run.id,
        prompt_id=prompt_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
    )
    answers = _load_prompt_answers_page(
        db,
        run_id=run.id,
        prompt_id=prompt_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        page=page,
        page_size=page_size,
    )

    brand_ids = {
        result.brand_id for answer in answers for result in answer.brand_results
    }
    brand_names: dict[int, str] = {}
    if brand_ids:
        brands = list(
            db.execute(
                select(Brand).where(
                    Brand.id.in_(brand_ids),
                    Brand.is_deleted.is_(False),
                )
            )
            .scalars()
            .all()
        )
        brand_names = {brand.id: brand.brand_name for brand in brands}

    items = [
        _serialize_answer_detail(answer, prompt=prompt, brand_names=brand_names)
        for answer in answers
    ]
    return {
        "run_id": run.id,
        "prompt_id": prompt_id,
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
