"""监测运行 API。"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.schemas import (
    MonitorRunOut,
    QueryTaskOut,
    QueryTaskStatus,
    RunCreate,
    RunStatus,
)
from app.geo_monitoring.services import runs as run_service

router = APIRouter()


def _list_query_tasks(
    db: Session,
    *,
    run_id: int,
    page: int,
    page_size: int,
    status: QueryTaskStatus | None,
    platform_code: str | None,
) -> dict:
    items, total = run_service.list_query_tasks(
        db,
        run_id=run_id,
        page=page,
        page_size=page_size,
        status=status.value if status else None,
        platform_code=platform_code,
    )
    data = [QueryTaskOut.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.get("/runs", summary="分页查询监测运行")
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    project_id: int | None = Query(None, ge=1),
    status: RunStatus | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    items, total = run_service.list_runs(
        db,
        page=page,
        page_size=page_size,
        project_id=project_id,
        status=status.value if status else None,
    )
    data = [MonitorRunOut.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("/runs", summary="创建监测运行")
def create_run(payload: RunCreate, db: Session = Depends(get_db)) -> dict:
    run = run_service.create_run(db, payload)
    return success(MonitorRunOut.model_validate(run).model_dump(mode="json"))


@router.get("/runs/{run_id}", summary="获取监测运行详情")
def get_run(run_id: int = Path(..., ge=1), db: Session = Depends(get_db)) -> dict:
    run = run_service.get_run_detail(db, run_id)
    return success(run.model_dump(mode="json"))


@router.get("/runs/{run_id}/query-tasks", summary="分页查询运行任务")
def list_query_tasks(
    run_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    status: QueryTaskStatus | None = Query(None),
    platform_code: str | None = Query(None, max_length=32),
    db: Session = Depends(get_db),
) -> dict:
    return _list_query_tasks(
        db,
        run_id=run_id,
        page=page,
        page_size=page_size,
        status=status,
        platform_code=platform_code,
    )


@router.get("/runs/{run_id}/tasks", summary="分页查询运行任务（别名）")
def list_tasks(
    run_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    status: QueryTaskStatus | None = Query(None),
    platform_code: str | None = Query(None, max_length=32),
    db: Session = Depends(get_db),
) -> dict:
    return _list_query_tasks(
        db,
        run_id=run_id,
        page=page,
        page_size=page_size,
        status=status,
        platform_code=platform_code,
    )
