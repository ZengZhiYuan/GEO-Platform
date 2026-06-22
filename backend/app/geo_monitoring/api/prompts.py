"""提示词 API。"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.schemas import (
    PromptCreate,
    PromptOut,
    PromptSetCreate,
    PromptSetOut,
    PromptSetStatus,
    PromptSetUpdate,
    PromptUpdate,
)
from app.geo_monitoring.services import prompts as prompt_service

router = APIRouter()


@router.get("/projects/{project_id}/prompt-sets", summary="分页查询提示词集")
# 分页查询项目下的提示词集列表
def list_prompt_sets(
    project_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: PromptSetStatus | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    items, total = prompt_service.list_prompt_sets(
        db,
        project_id=project_id,
        page=page,
        page_size=page_size,
        status=status.value if status else None,
    )
    data = [PromptSetOut.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("/projects/{project_id}/prompt-sets", summary="创建提示词集")
# 在指定项目下创建提示词集
def create_prompt_set(
    payload: PromptSetCreate,
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    prompt_set = prompt_service.create_prompt_set(db, project_id, payload)
    return success(PromptSetOut.model_validate(prompt_set).model_dump(mode="json"))


@router.get("/prompt-sets/{prompt_set_id}", summary="获取提示词集")
# 按 ID 获取提示词集详情
def get_prompt_set(
    prompt_set_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    prompt_set = prompt_service.get_prompt_set(db, prompt_set_id)
    return success(PromptSetOut.model_validate(prompt_set).model_dump(mode="json"))


@router.put("/prompt-sets/{prompt_set_id}", summary="更新提示词集")
# 更新提示词集信息
def update_prompt_set(
    payload: PromptSetUpdate,
    prompt_set_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    prompt_set = prompt_service.update_prompt_set(db, prompt_set_id, payload)
    return success(PromptSetOut.model_validate(prompt_set).model_dump(mode="json"))


@router.delete("/prompt-sets/{prompt_set_id}", summary="删除提示词集")
# 软删除指定提示词集
def delete_prompt_set(
    prompt_set_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    prompt_service.delete_prompt_set(db, prompt_set_id)
    return success({"id": prompt_set_id})


@router.post("/prompt-sets/{prompt_set_id}/activate", summary="激活提示词集")
# 激活指定提示词集并归档同项目其他激活版本
def activate_prompt_set(
    prompt_set_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    prompt_set = prompt_service.activate_prompt_set(db, prompt_set_id)
    return success(PromptSetOut.model_validate(prompt_set).model_dump(mode="json"))


@router.get("/prompt-sets/{prompt_set_id}/prompts", summary="分页查询提示词")
# 分页查询提示词集下的提示词列表
def list_prompts(
    prompt_set_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    items, total = prompt_service.list_prompts(
        db, prompt_set_id=prompt_set_id, page=page, page_size=page_size
    )
    data = [PromptOut.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("/prompt-sets/{prompt_set_id}/prompts", summary="创建提示词")
# 在提示词集下创建提示词
def create_prompt(
    payload: PromptCreate,
    prompt_set_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    prompt = prompt_service.create_prompt(db, prompt_set_id, payload)
    return success(PromptOut.model_validate(prompt).model_dump(mode="json"))


@router.put("/prompts/{prompt_id}", summary="更新提示词")
# 更新提示词内容或属性
def update_prompt(
    payload: PromptUpdate,
    prompt_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    prompt = prompt_service.update_prompt(db, prompt_id, payload)
    return success(PromptOut.model_validate(prompt).model_dump(mode="json"))


@router.delete("/prompts/{prompt_id}", summary="删除提示词")
# 软删除指定提示词
def delete_prompt(
    prompt_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    prompt_service.delete_prompt(db, prompt_id)
    return success({"id": prompt_id})
