"""监测项目仓储。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.geo_monitoring.models import MonitorProject, MonitorRun


# 按 ID 查询未删除的监测项目
def get_by_id(db: Session, project_id: int) -> MonitorProject | None:
    return db.execute(
        select(MonitorProject).where(
            MonitorProject.id == project_id,
            MonitorProject.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


# 分页查询监测项目，支持按名称与状态筛选
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


# 查询全部未删除项目，按 ID 倒序（供轻量切换器等全量列表使用）
def list_all_projects(db: Session) -> list[MonitorProject]:
    return list(
        db.execute(
            select(MonitorProject)
            .where(MonitorProject.is_deleted.is_(False))
            .order_by(MonitorProject.id.desc())
        )
        .scalars()
        .all()
    )


# 将监测项目实体加入当前会话
def add(db: Session, project: MonitorProject) -> None:
    db.add(project)


# 判断项目是否已有监测运行记录
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
