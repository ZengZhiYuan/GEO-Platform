"""监测项目服务。"""

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import MonitorProject
from app.geo_monitoring.repositories import projects as project_repo
from app.geo_monitoring.services.tenant_access import (
    ensure_tenant_access,
    list_tenant_filter,
    stamp_tenant_fields,
)
from app.geo_monitoring.schemas import (
    MonitorSetupSave,
    ProjectCreate,
    ProjectOut,
    ProjectSetupCreate,
    ProjectSetupOut,
    ProjectUpdate,
    RunCreate,
)


# 按 ID 查询监测项目，不存在则抛业务异常
def get_project(db: Session, project_id: int) -> MonitorProject:
    project = project_repo.get_by_id(db, project_id)
    if project is None:
        raise BusinessException(message="监测项目不存在", code=40400)
    ensure_tenant_access(project.tenant_id, resource_label="监测项目")
    return project


# 校验项目存在且处于 active 状态
def require_active_project(db: Session, project_id: int) -> MonitorProject:
    project = get_project(db, project_id)
    if project.status != "active":
        raise BusinessException(message="监测项目未启用", code=40001)
    return project


# 校验项目监测未暂停
def require_monitoring_not_paused(project: MonitorProject) -> None:
    if project.monitoring_paused:
        raise BusinessException(message="项目监测已暂停，无法启动新的监测运行", code=40054)


# 分页列出监测项目
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
        tenant_id=list_tenant_filter(),
    )


# 创建新的监测项目并设为 active
def create_project(db: Session, payload: ProjectCreate) -> MonitorProject:
    project = MonitorProject(**payload.model_dump(), status="active")
    stamp_tenant_fields(project)
    project_repo.add(db, project)
    db.commit()
    db.refresh(project)
    return project


def _validate_run_after_create_preconditions(
    monitor_setup: MonitorSetupSave,
    prompt_set,
) -> None:
    if prompt_set.prompt_count <= 0:
        raise BusinessException(
            message="创建后运行需要至少一个监测问题",
            code=40901,
            status_code=409,
        )
    if not monitor_setup.activate_prompt_set:
        raise BusinessException(message="创建后运行需要激活问题集", code=40055)


# 一步创建项目并保存监测设置，失败时不留下半成品项目
def setup_project(db: Session, payload: ProjectSetupCreate) -> ProjectSetupOut:
    from app.geo_monitoring.services import monitor_setup as monitor_setup_service
    from app.geo_monitoring.services import runs as run_service
    from app.geo_monitoring.services.prompts import activate_prompt_set
    from app.geo_monitoring.schemas import MonitorRunOut

    project = MonitorProject(**payload.project.model_dump(), status="active")
    stamp_tenant_fields(project)
    try:
        project_repo.add(db, project)
        db.flush()
        prompt_set = monitor_setup_service.persist_monitor_setup(
            db, project, payload.monitor_setup
        )
        if payload.run_after_create:
            _validate_run_after_create_preconditions(
                payload.monitor_setup, prompt_set
            )
        if (
            payload.monitor_setup.activate_prompt_set
            and prompt_set.prompt_count > 0
        ):
            db.flush()
            activate_prompt_set(db, prompt_set.id, commit=False)
        if payload.run_after_create:
            db.flush()
            run_service.prepare_run_create(
                db, RunCreate(project_id=project.id)
            )
        db.commit()
        db.refresh(project)
    except BusinessException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    monitor_setup = monitor_setup_service.get_monitor_setup(db, project.id)
    run_out: MonitorRunOut | None = None
    if payload.run_after_create:
        run = run_service.create_run(
            db, RunCreate(project_id=project.id)
        )
        run_out = MonitorRunOut.model_validate(run)

    return ProjectSetupOut(
        project=ProjectOut.model_validate(project),
        monitor_setup=monitor_setup,
        run=run_out,
    )


# 更新监测项目字段
def update_project(
    db: Session, project_id: int, payload: ProjectUpdate
) -> MonitorProject:
    project = get_project(db, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value.value if isinstance(value, StrEnum) else value)
    db.commit()
    db.refresh(project)
    return project


# 软删除项目，已被运行引用则拒绝
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


# 暂停项目监测：不影响历史数据，仅阻止调度与新运行
def pause_project(db: Session, project_id: int) -> MonitorProject:
    project = get_project(db, project_id)
    project.monitoring_paused = True
    db.commit()
    db.refresh(project)
    return project


# 恢复项目监测
def resume_project(db: Session, project_id: int) -> MonitorProject:
    project = get_project(db, project_id)
    project.monitoring_paused = False
    db.commit()
    db.refresh(project)
    return project
