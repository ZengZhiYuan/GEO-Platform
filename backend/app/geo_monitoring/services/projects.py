"""监测项目服务。"""

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import MonitorProject
from app.geo_monitoring.schemas import ProjectCreate, ProjectUpdate


def get_project(db: Session, project_id: int) -> MonitorProject:
    project = db.execute(
        select(MonitorProject).where(
            MonitorProject.id == project_id,
            MonitorProject.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if project is None:
        raise BusinessException(message="监测项目不存在", code=40400)
    return project


def require_active_project(db: Session, project_id: int) -> MonitorProject:
    project = get_project(db, project_id)
    if project.status != "active":
        raise BusinessException(message="监测项目未启用", code=40001)
    return project


def list_projects(
    db: Session,
    *,
    page: int,
    page_size: int,
    project_name: str | None = None,
    status: str | None = None,
) -> tuple[list[MonitorProject], int]:
    conditions = [MonitorProject.is_deleted.is_(False)]
    if project_name:
        conditions.append(MonitorProject.project_name.ilike(f"%{project_name.strip()}%"))
    if status:
        conditions.append(MonitorProject.status == status)

    total = db.execute(
        select(func.count()).select_from(MonitorProject).where(*conditions)
    ).scalar_one()
    items = list(
        db.execute(
            select(MonitorProject)
            .where(*conditions)
            .order_by(MonitorProject.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


def create_project(db: Session, payload: ProjectCreate) -> MonitorProject:
    project = MonitorProject(**payload.model_dump(), status="active")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(
    db: Session, project_id: int, payload: ProjectUpdate
) -> MonitorProject:
    project = get_project(db, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value.value if isinstance(value, StrEnum) else value)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_id: int) -> None:
    project = get_project(db, project_id)
    project.is_deleted = True
    project.deleted_at = datetime.now(timezone.utc)
    db.commit()
