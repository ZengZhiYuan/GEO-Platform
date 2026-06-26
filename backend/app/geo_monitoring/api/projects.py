"""监测项目 API。"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.schemas import (
    ProjectCreate,
    ProjectOut,
    ProjectSetupCreate,
    ProjectStatus,
    ProjectUpdate,
)
from app.geo_monitoring.services import projects as project_service
from app.geo_monitoring.services import project_overview as project_overview_service

router = APIRouter()


@router.get("/projects", summary="分页查询监测项目")
# 分页查询监测项目列表
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    project_name: str | None = Query(None),
    status: ProjectStatus | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    items, total = project_service.list_projects(
        db,
        page=page,
        page_size=page_size,
        project_name=project_name,
        status=status.value if status else None,
    )
    data = [ProjectOut.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("/projects", summary="创建监测项目")
# 创建新的监测项目
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    project = project_service.create_project(db, payload)
    return success(ProjectOut.model_validate(project).model_dump(mode="json"))


@router.post("/projects:setup", summary="一步创建项目并保存监测设置")
def setup_project(
    payload: ProjectSetupCreate, db: Session = Depends(get_db)
) -> dict:
    result = project_service.setup_project(db, payload)
    return success(result.model_dump(mode="json"))


@router.get("/projects/{project_id}", summary="获取监测项目")
# 按 ID 获取监测项目详情
def get_project(
    project_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    project = project_service.get_project(db, project_id)
    return success(ProjectOut.model_validate(project).model_dump(mode="json"))


@router.put("/projects/{project_id}", summary="更新监测项目")
# 更新监测项目信息
def update_project(
    payload: ProjectUpdate,
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    project = project_service.update_project(db, project_id, payload)
    return success(ProjectOut.model_validate(project).model_dump(mode="json"))


@router.delete("/projects/{project_id}", summary="删除监测项目")
# 软删除指定监测项目
def delete_project(
    project_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    project_service.delete_project(db, project_id)
    return success({"id": project_id})


@router.post("/projects/{project_id}/pause", summary="暂停项目监测")
def pause_project(
    project_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    project = project_service.pause_project(db, project_id)
    return success(ProjectOut.model_validate(project).model_dump(mode="json"))


@router.post("/projects/{project_id}/resume", summary="恢复项目监测")
def resume_project(
    project_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    project = project_service.resume_project(db, project_id)
    return success(ProjectOut.model_validate(project).model_dump(mode="json"))


@router.get("/projects/{project_id}/delete-check", summary="删除前关联检查")
def delete_check_project(
    project_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    payload = project_overview_service.get_delete_check(db, project_id)
    return success(payload.model_dump(mode="json"))
