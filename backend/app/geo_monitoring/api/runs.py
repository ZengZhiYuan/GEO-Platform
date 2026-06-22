"""监测运行 API。"""

from datetime import datetime

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


# 查询子任务分页响应的共用逻辑
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
# 分页查询监测运行，支持按项目、状态与时间范围筛选
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    project_id: int | None = Query(None, ge=1),
    status: RunStatus | None = Query(None),
    created_after: datetime | None = Query(None),
    created_before: datetime | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    items, total = run_service.list_runs(
        db,
        page=page,
        page_size=page_size,
        project_id=project_id,
        status=status.value if status else None,
        created_after=created_after,
        created_before=created_before,
    )
    data = [MonitorRunOut.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("/runs", summary="创建监测运行")
# 创建新的监测运行并生成查询子任务
def create_run(payload: RunCreate, db: Session = Depends(get_db)) -> dict:
    run = run_service.create_run(db, payload)
    return success(MonitorRunOut.model_validate(run).model_dump(mode="json"))


@router.get("/runs/{run_id}", summary="获取监测运行详情")
# 获取监测运行详情及汇总统计
def get_run(run_id: int = Path(..., ge=1), db: Session = Depends(get_db)) -> dict:
    run = run_service.get_run_detail(db, run_id)
    return success(run.model_dump(mode="json"))


@router.post("/runs/{run_id}/cancel", summary="取消监测运行")
# 取消进行中的监测运行
def cancel_run(run_id: int = Path(..., ge=1), db: Session = Depends(get_db)) -> dict:
    run = run_service.cancel_run(db, run_id)
    return success(MonitorRunOut.model_validate(run).model_dump(mode="json"))


@router.post("/runs/{run_id}/retry-failed", summary="重试失败任务")
# 重试运行中失败的查询子任务
def retry_failed(run_id: int = Path(..., ge=1), db: Session = Depends(get_db)) -> dict:
    run, retried_count = run_service.retry_failed_tasks(db, run_id)
    payload = MonitorRunOut.model_validate(run).model_dump(mode="json")
    payload["retried_count"] = retried_count
    return success(payload)


@router.get("/runs/{run_id}/query-tasks", summary="分页查询运行任务")
# 分页查询运行下的查询子任务
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
# 查询子任务分页接口的别名路由
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
