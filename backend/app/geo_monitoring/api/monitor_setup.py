"""品牌诊断/监控统一设置 API。"""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.geo_monitoring.schemas import MonitorSetupSave
from app.geo_monitoring.services import monitor_setup as monitor_setup_service

router = APIRouter()


@router.get("/projects/{project_id}/monitor-setup", summary="获取监测设置")
def get_monitor_setup(
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    data = monitor_setup_service.get_monitor_setup(db, project_id)
    return success(data)


@router.put("/projects/{project_id}/monitor-setup", summary="保存监测设置")
def save_monitor_setup(
    payload: MonitorSetupSave,
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    data = monitor_setup_service.save_monitor_setup(db, project_id, payload)
    return success(data)
