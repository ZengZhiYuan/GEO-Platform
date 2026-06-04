"""写作任务 API Router。

路径前缀由 app/api/router.py include 时指定（最终为 /api/writing-tasks）。
接口集合对齐 docs/api-contract.md：
    GET    /api/writing-tasks            分页列表
    POST   /api/writing-tasks            创建大任务（自动拆分小任务）
    GET    /api/writing-tasks/{id}       任务详情
    POST   /api/writing-tasks/{id}/cancel  取消任务
    POST   /api/writing-tasks/{id}/retry   重试任务（占位）

所有接口返回统一响应格式：{"code": 0, "message": "success", "data": ...}
"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.schemas.writing_task import WritingTaskCreate, WritingTaskOut
from app.services import writing_task as writing_task_service

router = APIRouter(prefix="/writing-tasks", tags=["写作任务"])


@router.get("", summary="分页查询写作任务")
def list_writing_tasks(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    task_name: str | None = Query(None, description="按任务名称模糊搜索"),
    task_status: str | None = Query(None, description="按任务状态精确筛选"),
    db: Session = Depends(get_db),
) -> dict:
    items, total = writing_task_service.list_writing_tasks(
        db,
        page=page,
        page_size=page_size,
        task_name=task_name,
        task_status=task_status,
    )
    data = [
        WritingTaskOut.model_validate(item).model_dump(mode="json") for item in items
    ]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("", summary="创建写作任务（自动拆分小任务）")
def create_writing_task(
    payload: WritingTaskCreate,
    db: Session = Depends(get_db),
) -> dict:
    task = writing_task_service.create_writing_task(db, payload)
    return success(WritingTaskOut.model_validate(task).model_dump(mode="json"))


@router.get("/{task_id}", summary="获取写作任务详情")
def get_writing_task(
    task_id: int = Path(..., ge=1, description="写作任务 ID"),
    db: Session = Depends(get_db),
) -> dict:
    task = writing_task_service.get_writing_task(db, task_id)
    return success(WritingTaskOut.model_validate(task).model_dump(mode="json"))


@router.post("/{task_id}/cancel", summary="取消写作任务")
def cancel_writing_task(
    task_id: int = Path(..., ge=1, description="写作任务 ID"),
    db: Session = Depends(get_db),
) -> dict:
    task = writing_task_service.cancel_writing_task(db, task_id)
    return success(WritingTaskOut.model_validate(task).model_dump(mode="json"))


@router.post("/{task_id}/retry", summary="重试写作任务（占位）")
def retry_writing_task(
    task_id: int = Path(..., ge=1, description="写作任务 ID"),
    db: Session = Depends(get_db),
) -> dict:
    task = writing_task_service.retry_writing_task(db, task_id)
    return success(WritingTaskOut.model_validate(task).model_dump(mode="json"))
