"""AI 生成辅助 API。"""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.geo_monitoring.schemas import (
    AiBrandWordsGenerateIn,
    AiCompetitorsGenerateIn,
    AiQuestionsGenerateIn,
)
from app.geo_monitoring.services import ai_generation as ai_generation_service

router = APIRouter()


@router.post(
    "/ai/brand-words:generate",
    summary="AI 生成品牌词候选（无 project_id，创建向导推荐）",
)
def generate_brand_words_global(payload: AiBrandWordsGenerateIn) -> dict:
    data = ai_generation_service.generate_brand_words(payload)
    return success(data)


@router.post(
    "/ai/competitors:generate",
    summary="AI 生成竞品候选（无 project_id，创建向导推荐）",
)
def generate_competitors_global(payload: AiCompetitorsGenerateIn) -> dict:
    data = ai_generation_service.generate_competitors(payload)
    return success(data)


@router.post(
    "/ai/questions:generate",
    summary="AI 生成监测问题候选（无 project_id，创建向导推荐）",
)
def generate_questions_global(payload: AiQuestionsGenerateIn) -> dict:
    data = ai_generation_service.generate_questions(payload)
    return success(data)


@router.post(
    "/projects/{project_id}/ai/brand-words:generate",
    summary="AI 生成品牌词候选",
)
def generate_brand_words(
    payload: AiBrandWordsGenerateIn,
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    data = ai_generation_service.generate_brand_words_for_project(
        db, project_id, payload
    )
    return success(data)


@router.post(
    "/projects/{project_id}/ai/competitors:generate",
    summary="AI 生成竞品候选",
)
def generate_competitors(
    payload: AiCompetitorsGenerateIn,
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    data = ai_generation_service.generate_competitors_for_project(
        db, project_id, payload
    )
    return success(data)


@router.post(
    "/projects/{project_id}/ai/questions:generate",
    summary="AI 生成监测问题候选",
)
def generate_questions(
    payload: AiQuestionsGenerateIn,
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    data = ai_generation_service.generate_questions_for_project(
        db, project_id, payload
    )
    return success(data)
