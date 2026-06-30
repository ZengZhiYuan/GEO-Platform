"""核心词服务。"""

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import CoreKeyword
from app.geo_monitoring.repositories import core_keywords as core_keyword_repo
from app.geo_monitoring.schemas import CoreKeywordCreate, CoreKeywordUpdate
from app.geo_monitoring.services.projects import require_active_project
from app.geo_monitoring.services.tenant_access import ensure_project_tenant_access


def _commit_unique(db: Session, *, code: int, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessException(message=message, code=code) from exc


def get_core_keyword(db: Session, keyword_id: int) -> CoreKeyword:
    keyword = core_keyword_repo.get_by_id(db, keyword_id)
    if keyword is None:
        raise BusinessException(message="核心词不存在", code=40400)
    ensure_project_tenant_access(db, keyword.project_id)
    return keyword


def list_core_keywords(
    db: Session,
    *,
    project_id: int,
    page: int,
    page_size: int,
    enabled: bool | None = None,
) -> tuple[list[CoreKeyword], int]:
    require_active_project(db, project_id)
    return core_keyword_repo.list_keywords(
        db,
        project_id=project_id,
        page=page,
        page_size=page_size,
        enabled=enabled,
    )


def create_core_keyword(
    db: Session, project_id: int, payload: CoreKeywordCreate
) -> CoreKeyword:
    require_active_project(db, project_id)
    if (
        core_keyword_repo.find_duplicate(db, project_id, payload.keyword)
        is not None
    ):
        raise BusinessException(message="项目内核心词不能重复", code=40024)
    keyword = CoreKeyword(
        project_id=project_id,
        **{
            key: value.value if isinstance(value, StrEnum) else value
            for key, value in payload.model_dump().items()
        },
    )
    core_keyword_repo.add(db, keyword)
    _commit_unique(db, code=40024, message="项目内核心词不能重复")
    db.refresh(keyword)
    return keyword


def update_core_keyword(
    db: Session, keyword_id: int, payload: CoreKeywordUpdate
) -> CoreKeyword:
    keyword = get_core_keyword(db, keyword_id)
    data = payload.model_dump(exclude_unset=True)
    if "keyword" in data and data["keyword"] != keyword.keyword:
        if (
            core_keyword_repo.find_duplicate(
                db,
                keyword.project_id,
                data["keyword"],
                exclude_id=keyword.id,
            )
            is not None
        ):
            raise BusinessException(message="项目内核心词不能重复", code=40024)
    for field, value in data.items():
        setattr(keyword, field, value)
    _commit_unique(db, code=40024, message="项目内核心词不能重复")
    db.refresh(keyword)
    return keyword


def delete_core_keyword(db: Session, keyword_id: int) -> None:
    keyword = get_core_keyword(db, keyword_id)
    keyword.is_deleted = True
    keyword.deleted_at = datetime.now(timezone.utc)
    db.commit()
