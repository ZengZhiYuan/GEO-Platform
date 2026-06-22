"""Prompt 词库 API。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.schemas import PromptLibraryOut
from app.geo_monitoring.services import prompt_library as prompt_library_service

router = APIRouter()


@router.get("/prompt-library", summary="分页查询 Prompt 词库")
def list_prompt_library(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    industry: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    items, total = prompt_library_service.list_prompt_library(
        db, page=page, page_size=page_size, industry=industry
    )
    data = [
        PromptLibraryOut.model_validate(item).model_dump(mode="json") for item in items
    ]
    return paginate(data, total=total, page=page, page_size=page_size)
