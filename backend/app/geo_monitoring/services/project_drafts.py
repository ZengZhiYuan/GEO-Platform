"""创建向导草稿服务。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import ProjectDraft
from app.geo_monitoring.repositories import project_drafts as draft_repo
from app.geo_monitoring.schemas import (
    ProjectDraftCreate,
    ProjectDraftOut,
    ProjectDraftUpdate,
)


def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _normalize_draft_key(draft_key: str | None) -> str | None:
    if draft_key is None:
        return None
    value = draft_key.strip()
    return value or None


def _ensure_draft_key_access(draft: ProjectDraft, draft_key: str) -> None:
    normalized_key = _normalize_draft_key(draft_key)
    if normalized_key is None or draft.draft_key != normalized_key:
        raise BusinessException(message="创建向导草稿不存在", code=40400)


def _to_out(draft: ProjectDraft) -> ProjectDraftOut:
    return ProjectDraftOut(
        id=draft.id,
        draft_key=draft.draft_key,
        current_step=draft.current_step,
        project=draft.project_data or {},
        monitor_setup=draft.monitor_setup_data or {},
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def get_project_draft(db: Session, draft_id: int, draft_key: str) -> ProjectDraftOut:
    draft = draft_repo.get_by_id(db, draft_id)
    if draft is None:
        raise BusinessException(message="创建向导草稿不存在", code=40400)
    _ensure_draft_key_access(draft, draft_key)
    return _to_out(draft)


def get_current_project_draft(db: Session, draft_key: str) -> ProjectDraftOut:
    normalized_key = _normalize_draft_key(draft_key)
    if normalized_key is None:
        raise BusinessException(message="创建向导草稿不存在", code=40400)
    draft = draft_repo.get_latest_by_draft_key(db, normalized_key)
    if draft is None:
        raise BusinessException(message="创建向导草稿不存在", code=40400)
    return _to_out(draft)


def create_project_draft(db: Session, payload: ProjectDraftCreate) -> ProjectDraftOut:
    draft = ProjectDraft(
        draft_key=_normalize_draft_key(payload.draft_key),
        current_step=payload.current_step,
        project_data=payload.project,
        monitor_setup_data=payload.monitor_setup,
    )
    draft_repo.add(db, draft)
    db.commit()
    db.refresh(draft)
    return _to_out(draft)


def _apply_update(draft: ProjectDraft, payload: ProjectDraftUpdate) -> None:
    if payload.draft_key is not None:
        draft.draft_key = _normalize_draft_key(payload.draft_key)
    if payload.current_step is not None:
        draft.current_step = payload.current_step
    if payload.project is not None:
        draft.project_data = _deep_merge_dict(draft.project_data or {}, payload.project)
    if payload.monitor_setup is not None:
        draft.monitor_setup_data = _deep_merge_dict(
            draft.monitor_setup_data or {},
            payload.monitor_setup,
        )


def update_project_draft(
    db: Session, draft_id: int, draft_key: str, payload: ProjectDraftUpdate
) -> ProjectDraftOut:
    draft = draft_repo.get_by_id(db, draft_id)
    if draft is None:
        raise BusinessException(message="创建向导草稿不存在", code=40400)
    _ensure_draft_key_access(draft, draft_key)
    _apply_update(draft, payload)
    db.commit()
    db.refresh(draft)
    return _to_out(draft)


def upsert_current_project_draft(
    db: Session, payload: ProjectDraftCreate
) -> ProjectDraftOut:
    normalized_key = _normalize_draft_key(payload.draft_key)
    if normalized_key is None:
        raise BusinessException(message="draft_key 不能为空", code=422)

    draft = draft_repo.get_latest_by_draft_key(db, normalized_key)
    if draft is None:
        return create_project_draft(
            db,
            ProjectDraftCreate(
                draft_key=normalized_key,
                current_step=payload.current_step,
                project=payload.project,
                monitor_setup=payload.monitor_setup,
            ),
        )

    update_payload = ProjectDraftUpdate(
        draft_key=normalized_key,
        current_step=payload.current_step,
        project=payload.project or None,
        monitor_setup=payload.monitor_setup or None,
    )
    _apply_update(draft, update_payload)
    db.commit()
    db.refresh(draft)
    return _to_out(draft)
