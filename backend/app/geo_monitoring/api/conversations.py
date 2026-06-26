"""AI 对话记录问题聚合 API。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ResponseModel, success
from app.geo_monitoring.schemas import EvaluationTagsOut
from app.geo_monitoring.services import conversations as conversations_service
from app.geo_monitoring.services import evaluation_tags as evaluation_tags_service
from app.geo_monitoring.services.exports import csv_file_response

router = APIRouter()


@router.get(
    "/projects/{project_id}/conversation-questions",
    summary="按 AI 问题聚合对话记录主表",
)
def list_conversation_questions(
    project_id: int = Path(..., ge=1),
    run_id: int | None = Query(None, ge=1, description="指定运行 ID，默认取最近已分析或已终态 run"),
    platform_codes: list[str] | None = Query(None),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    keyword: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    data = conversations_service.list_conversation_questions(
        db,
        project_id,
        run_id=run_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return success(data)


@router.get(
    "/projects/{project_id}/conversation-questions/{prompt_id}/answers",
    summary="获取指定问题下各平台回答详情",
)
def list_conversation_question_answers(
    project_id: int = Path(..., ge=1),
    prompt_id: int = Path(..., ge=1),
    run_id: int | None = Query(None, ge=1),
    platform_codes: list[str] | None = Query(None),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    data = conversations_service.list_conversation_question_answers(
        db,
        project_id,
        prompt_id,
        run_id=run_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        page=page,
        page_size=page_size,
    )
    return success(data)


@router.get(
    "/projects/{project_id}/conversation-questions/{prompt_id}/evaluation-tags",
    summary="高频评价标签规则聚类",
    response_model=ResponseModel[EvaluationTagsOut],
)
def list_evaluation_tags(
    project_id: int = Path(..., ge=1),
    prompt_id: int = Path(..., ge=1),
    run_id: int | None = Query(None, ge=1),
    platform_codes: list[str] | None = Query(None),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    data = evaluation_tags_service.cluster_evaluation_tags(
        db,
        project_id,
        prompt_id,
        run_id=run_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    )
    return success(data)


@router.get(
    "/projects/{project_id}/conversation-questions/export",
    summary="导出 AI 对话记录主表 CSV",
)
def export_conversation_questions(
    project_id: int = Path(..., ge=1),
    run_id: int | None = Query(None, ge=1),
    platform_codes: list[str] | None = Query(None),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    keyword: str | None = Query(None, max_length=200),
    db: Session = Depends(get_db),
):
    headers, rows = conversations_service.export_conversation_questions_rows(
        db,
        project_id,
        run_id=run_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        keyword=keyword,
    )
    return csv_file_response(
        filename=f"conversation-questions-{project_id}.csv",
        headers=headers,
        rows=rows,
    )
