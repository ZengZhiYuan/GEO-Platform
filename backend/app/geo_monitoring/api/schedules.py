"""调度 API。"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.schemas import MonitorRunOut, ScheduleCreate, ScheduleOut, ScheduleUpdate
from app.geo_monitoring.services import schedules as schedule_service

router = APIRouter()


@router.get("/projects/{project_id}/schedules", summary="分页查询项目调度")
# 分页查询项目下的监测调度配置
def list_schedules(
    project_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    items, total = schedule_service.list_schedules(
        db, project_id=project_id, page=page, page_size=page_size
    )
    data = [ScheduleOut.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("/projects/{project_id}/schedules", summary="创建监测调度")
# 为项目创建定时监测调度
def create_schedule(
    payload: ScheduleCreate,
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    schedule = schedule_service.create_schedule(db, project_id, payload)
    return success(ScheduleOut.model_validate(schedule).model_dump(mode="json"))


@router.get("/schedules/{schedule_id}", summary="获取监测调度")
# 按 ID 获取监测调度详情
def get_schedule(
    schedule_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    schedule = schedule_service.get_schedule(db, schedule_id)
    return success(ScheduleOut.model_validate(schedule).model_dump(mode="json"))


@router.put("/schedules/{schedule_id}", summary="更新监测调度")
# 更新监测调度的配置
def update_schedule(
    payload: ScheduleUpdate,
    schedule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    schedule = schedule_service.update_schedule(db, schedule_id, payload)
    return success(ScheduleOut.model_validate(schedule).model_dump(mode="json"))


@router.delete("/schedules/{schedule_id}", summary="删除监测调度")
# 软删除指定监测调度
def delete_schedule(
    schedule_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    schedule_service.delete_schedule(db, schedule_id)
    return success({})


@router.post("/schedules/{schedule_id}/enable", summary="启用监测调度")
# 启用监测调度
def enable_schedule(
    schedule_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    schedule = schedule_service.set_schedule_enabled(db, schedule_id, True)
    return success(ScheduleOut.model_validate(schedule).model_dump(mode="json"))


@router.post("/schedules/{schedule_id}/disable", summary="停用监测调度")
# 停用监测调度
def disable_schedule(
    schedule_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    schedule = schedule_service.set_schedule_enabled(db, schedule_id, False)
    return success(ScheduleOut.model_validate(schedule).model_dump(mode="json"))


@router.post("/schedules/{schedule_id}/trigger", summary="立即触发监测调度")
# 立即手动触发一次监测运行
def trigger_schedule(
    schedule_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    run = schedule_service.trigger_schedule_now(db, schedule_id)
    return success(MonitorRunOut.model_validate(run).model_dump(mode="json"))
