"""创建向导草稿 API。"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.geo_monitoring.schemas import ProjectDraftCreate, ProjectDraftUpdate
from app.geo_monitoring.services import project_drafts as project_draft_service

router = APIRouter()


@router.post("/project-drafts", summary="创建向导草稿")
def create_project_draft(
    payload: ProjectDraftCreate, db: Session = Depends(get_db)
) -> dict:
    data = project_draft_service.create_project_draft(db, payload)
    return success(data.model_dump(mode="json"))


@router.put("/project-drafts", summary="按 draft_key 更新或创建向导草稿")
def upsert_project_draft(
    payload: ProjectDraftCreate, db: Session = Depends(get_db)
) -> dict:
    data = project_draft_service.upsert_current_project_draft(db, payload)
    return success(data.model_dump(mode="json"))


@router.put("/project-drafts/current", summary="按 draft_key 更新或创建向导草稿")
def upsert_current_project_draft(
    payload: ProjectDraftCreate, db: Session = Depends(get_db)
) -> dict:
    data = project_draft_service.upsert_current_project_draft(db, payload)
    return success(data.model_dump(mode="json"))


@router.get("/project-drafts/current", summary="按 draft_key 获取最新向导草稿")
def get_current_project_draft(
    draft_key: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> dict:
    data = project_draft_service.get_current_project_draft(db, draft_key)
    return success(data.model_dump(mode="json"))


@router.put("/project-drafts/{draft_id}", summary="更新向导草稿")
def update_project_draft(
    payload: ProjectDraftUpdate,
    draft_id: int = Path(..., ge=1),
    draft_key: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> dict:
    data = project_draft_service.update_project_draft(
        db, draft_id, draft_key, payload
    )
    return success(data.model_dump(mode="json"))


@router.get("/project-drafts/{draft_id}", summary="获取向导草稿")
def get_project_draft(
    draft_id: int = Path(..., ge=1),
    draft_key: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> dict:
    data = project_draft_service.get_project_draft(db, draft_id, draft_key)
    return success(data.model_dump(mode="json"))
