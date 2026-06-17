"""监测项目仓储。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.geo_monitoring.models import MonitorProject, MonitorRun


def get_by_id(db: Session, project_id: int) -> MonitorProject | None:
    return db.execute(
        select(MonitorProject).where(
            MonitorProject.id == project_id,
            MonitorProject.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


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


def add(db: Session, project: MonitorProject) -> None:
    db.add(project)


def has_runs(db: Session, project_id: int) -> bool:
    return (
        db.execute(
            select(MonitorRun.id).where(
                MonitorRun.project_id == project_id,
                MonitorRun.is_deleted.is_(False),
            )
        ).first()
        is not None
    )
