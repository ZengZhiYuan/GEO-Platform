"""监测项目服务。"""

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import MonitorProject
from app.geo_monitoring.repositories import projects as project_repo
from app.geo_monitoring.schemas import ProjectCreate, ProjectUpdate


def get_project(db: Session, project_id: int) -> MonitorProject:
    project = project_repo.get_by_id(db, project_id)
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
    return project_repo.list_projects(
        db,
        page=page,
        page_size=page_size,
        project_name=project_name,
        status=status,
    )


def create_project(db: Session, payload: ProjectCreate) -> MonitorProject:
    project = MonitorProject(**payload.model_dump(), status="active")
    project_repo.add(db, project)
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
    if project_repo.has_runs(db, project_id):
        raise BusinessException(
            message="项目已被监测运行引用，无法删除",
            code=40903,
            status_code=409,
        )
    project.is_deleted = True
    project.deleted_at = datetime.now(timezone.utc)
    db.commit()
