"""项目概览 API。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.schemas import ProjectStatus
from app.geo_monitoring.services import project_overview as project_overview_service

router = APIRouter()


@router.get("/projects/options", summary="项目切换器轻量列表")
def list_project_options(db: Session = Depends(get_db)) -> dict:
    items = project_overview_service.list_project_options(db)
    data = [item.model_dump(mode="json") for item in items]
    return success({"items": data})


@router.get("/projects/overview", summary="项目卡片批量概览")
def list_project_overview(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    project_name: str | None = Query(None),
    status: ProjectStatus | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    items, total = project_overview_service.list_project_overview(
        db,
        page=page,
        page_size=page_size,
        project_name=project_name,
        status=status.value if status else None,
    )
    data = [item.model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)
