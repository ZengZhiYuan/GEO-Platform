"""AI 应用监测 API。"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.schemas import (
    AIPlatformOut,
    AIPlatformUpdate,
    BrandAliasCreate,
    BrandAliasOut,
    BrandAliasUpdate,
    BrandCreate,
    BrandOut,
    BrandType,
    BrandUpdate,
    EntityStatus,
    MonitorRunOut,
    ProjectCreate,
    ProjectOut,
    ProjectStatus,
    ProjectUpdate,
    PromptCreate,
    PromptOut,
    PromptSetCreate,
    PromptSetOut,
    PromptSetStatus,
    PromptSetUpdate,
    PromptUpdate,
    QueryTaskOut,
    QueryTaskStatus,
    RunCreate,
    RunStatus,
)
from app.geo_monitoring.services import brands as brand_service
from app.geo_monitoring.services import platforms as platform_service
from app.geo_monitoring.services import projects as project_service
from app.geo_monitoring.services import prompts as prompt_service
from app.geo_monitoring.services import runs as run_service

router = APIRouter(prefix="/geo-monitoring", tags=["AI 应用监测"])


@router.get("/platforms", summary="分页查询 AI 平台")
def list_platforms(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    enabled: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    items, total = platform_service.list_platforms(
        db, page=page, page_size=page_size, enabled=enabled
    )
    data = [AIPlatformOut.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.put("/platforms/{platform_code}", summary="更新 AI 平台配置")
def update_platform(
    payload: AIPlatformUpdate,
    platform_code: str = Path(..., min_length=1, max_length=32),
    db: Session = Depends(get_db),
) -> dict:
    platform = platform_service.update_platform(db, platform_code, payload)
    return success(AIPlatformOut.model_validate(platform).model_dump(mode="json"))


@router.get("/platforms/{platform_code}", summary="获取 AI 平台配置")
def get_platform(
    platform_code: str = Path(..., min_length=1, max_length=32),
    db: Session = Depends(get_db),
) -> dict:
    platform = platform_service.get_platform(db, platform_code)
    return success(AIPlatformOut.model_validate(platform).model_dump(mode="json"))


@router.get("/projects", summary="分页查询监测项目")
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
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    project = project_service.create_project(db, payload)
    return success(ProjectOut.model_validate(project).model_dump(mode="json"))


@router.get("/projects/{project_id}", summary="获取监测项目")
def get_project(
    project_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    project = project_service.get_project(db, project_id)
    return success(ProjectOut.model_validate(project).model_dump(mode="json"))


@router.put("/projects/{project_id}", summary="更新监测项目")
def update_project(
    payload: ProjectUpdate,
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    project = project_service.update_project(db, project_id, payload)
    return success(ProjectOut.model_validate(project).model_dump(mode="json"))


@router.delete("/projects/{project_id}", summary="删除监测项目")
def delete_project(
    project_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    project_service.delete_project(db, project_id)
    return success({"id": project_id})


@router.get("/projects/{project_id}/brands", summary="分页查询项目品牌")
def list_brands(
    project_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    brand_name: str | None = Query(None),
    brand_type: BrandType | None = Query(None),
    status: EntityStatus | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    items, total = brand_service.list_brands(
        db,
        project_id=project_id,
        page=page,
        page_size=page_size,
        brand_name=brand_name,
        brand_type=brand_type.value if brand_type else None,
        status=status.value if status else None,
    )
    data = [BrandOut.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("/projects/{project_id}/brands", summary="创建项目品牌")
def create_brand(
    payload: BrandCreate,
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    brand = brand_service.create_brand(db, project_id, payload)
    return success(BrandOut.model_validate(brand).model_dump(mode="json"))


@router.get("/brands/{brand_id}", summary="获取品牌")
def get_brand(
    brand_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    brand = brand_service.get_brand(db, brand_id)
    return success(BrandOut.model_validate(brand).model_dump(mode="json"))


@router.put("/brands/{brand_id}", summary="更新品牌")
def update_brand(
    payload: BrandUpdate,
    brand_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    brand = brand_service.update_brand(db, brand_id, payload)
    return success(BrandOut.model_validate(brand).model_dump(mode="json"))


@router.delete("/brands/{brand_id}", summary="删除品牌")
def delete_brand(
    brand_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    brand_service.delete_brand(db, brand_id)
    return success({"id": brand_id})


@router.get("/brands/{brand_id}/aliases", summary="分页查询品牌别名")
def list_brand_aliases(
    brand_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    items, total = brand_service.list_aliases(
        db, brand_id=brand_id, page=page, page_size=page_size
    )
    data = [
        BrandAliasOut.model_validate(item).model_dump(mode="json") for item in items
    ]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("/brands/{brand_id}/aliases", summary="创建品牌别名")
def create_brand_alias(
    payload: BrandAliasCreate,
    brand_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    alias = brand_service.create_alias(db, brand_id, payload)
    return success(BrandAliasOut.model_validate(alias).model_dump(mode="json"))


@router.put("/brand-aliases/{alias_id}", summary="更新品牌别名")
def update_brand_alias(
    payload: BrandAliasUpdate,
    alias_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    alias = brand_service.update_alias(db, alias_id, payload)
    return success(BrandAliasOut.model_validate(alias).model_dump(mode="json"))


@router.delete("/brand-aliases/{alias_id}", summary="删除品牌别名")
def delete_brand_alias(
    alias_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    brand_service.delete_alias(db, alias_id)
    return success({"id": alias_id})


@router.get("/projects/{project_id}/prompt-sets", summary="分页查询提示词集")
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
def create_prompt_set(
    payload: PromptSetCreate,
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    prompt_set = prompt_service.create_prompt_set(db, project_id, payload)
    return success(PromptSetOut.model_validate(prompt_set).model_dump(mode="json"))


@router.get("/prompt-sets/{prompt_set_id}", summary="获取提示词集")
def get_prompt_set(
    prompt_set_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    prompt_set = prompt_service.get_prompt_set(db, prompt_set_id)
    return success(PromptSetOut.model_validate(prompt_set).model_dump(mode="json"))


@router.put("/prompt-sets/{prompt_set_id}", summary="更新提示词集")
def update_prompt_set(
    payload: PromptSetUpdate,
    prompt_set_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    prompt_set = prompt_service.update_prompt_set(db, prompt_set_id, payload)
    return success(PromptSetOut.model_validate(prompt_set).model_dump(mode="json"))


@router.delete("/prompt-sets/{prompt_set_id}", summary="删除提示词集")
def delete_prompt_set(
    prompt_set_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    prompt_service.delete_prompt_set(db, prompt_set_id)
    return success({"id": prompt_set_id})


@router.post("/prompt-sets/{prompt_set_id}/activate", summary="激活提示词集")
def activate_prompt_set(
    prompt_set_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    prompt_set = prompt_service.activate_prompt_set(db, prompt_set_id)
    return success(PromptSetOut.model_validate(prompt_set).model_dump(mode="json"))


@router.get("/prompt-sets/{prompt_set_id}/prompts", summary="分页查询提示词")
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
def create_prompt(
    payload: PromptCreate,
    prompt_set_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    prompt = prompt_service.create_prompt(db, prompt_set_id, payload)
    return success(PromptOut.model_validate(prompt).model_dump(mode="json"))


@router.put("/prompts/{prompt_id}", summary="更新提示词")
def update_prompt(
    payload: PromptUpdate,
    prompt_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    prompt = prompt_service.update_prompt(db, prompt_id, payload)
    return success(PromptOut.model_validate(prompt).model_dump(mode="json"))


@router.delete("/prompts/{prompt_id}", summary="删除提示词")
def delete_prompt(
    prompt_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    prompt_service.delete_prompt(db, prompt_id)
    return success({"id": prompt_id})


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


@router.get("/runs/{run_id}", summary="获取监测运行")
def get_run(run_id: int = Path(..., ge=1), db: Session = Depends(get_db)) -> dict:
    run = run_service.get_run(db, run_id)
    return success(MonitorRunOut.model_validate(run).model_dump(mode="json"))


@router.get("/runs/{run_id}/query-tasks", summary="分页查询运行任务")
def list_query_tasks(
    run_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    status: QueryTaskStatus | None = Query(None),
    platform_code: str | None = Query(None, max_length=32),
    db: Session = Depends(get_db),
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
