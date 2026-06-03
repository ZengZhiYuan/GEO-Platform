"""标题灵感 API Router。

路径前缀由 app/api/router.py include 时指定（最终为 /api/title-inspirations）。
所有接口返回统一响应格式：{"code": 0, "message": "success", "data": ...}
"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.schemas.title_inspiration import (
    CollectStatus,
    TitleInspirationCreate,
    TitleInspirationOut,
    TitleInspirationUpdate,
)
from app.services import title_inspiration as title_inspiration_service

router = APIRouter(prefix="/title-inspirations", tags=["标题灵感"])


@router.get("", summary="分页查询标题灵感")
def list_title_inspirations(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    main_word: str | None = Query(None, description="按主词模糊搜索"),
    collect_status: CollectStatus | None = Query(None, description="按收录状态筛选"),
    db: Session = Depends(get_db),
) -> dict:
    items, total = title_inspiration_service.list_title_inspirations(
        db,
        page=page,
        page_size=page_size,
        main_word=main_word,
        collect_status=collect_status.value if collect_status else None,
    )
    data = [
        TitleInspirationOut.model_validate(item).model_dump(mode="json")
        for item in items
    ]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("", summary="新增标题灵感")
def create_title_inspiration(
    payload: TitleInspirationCreate,
    db: Session = Depends(get_db),
) -> dict:
    inspiration = title_inspiration_service.create_title_inspiration(db, payload)
    return success(
        TitleInspirationOut.model_validate(inspiration).model_dump(mode="json")
    )


@router.get("/{inspiration_id}", summary="获取标题灵感详情")
def get_title_inspiration(
    inspiration_id: int = Path(..., ge=1, description="标题灵感 ID"),
    db: Session = Depends(get_db),
) -> dict:
    inspiration = title_inspiration_service.get_title_inspiration(db, inspiration_id)
    return success(
        TitleInspirationOut.model_validate(inspiration).model_dump(mode="json")
    )


@router.put("/{inspiration_id}", summary="更新标题灵感")
def update_title_inspiration(
    payload: TitleInspirationUpdate,
    inspiration_id: int = Path(..., ge=1, description="标题灵感 ID"),
    db: Session = Depends(get_db),
) -> dict:
    inspiration = title_inspiration_service.update_title_inspiration(
        db, inspiration_id, payload
    )
    return success(
        TitleInspirationOut.model_validate(inspiration).model_dump(mode="json")
    )


@router.delete("/{inspiration_id}", summary="删除标题灵感")
def delete_title_inspiration(
    inspiration_id: int = Path(..., ge=1, description="标题灵感 ID"),
    db: Session = Depends(get_db),
) -> dict:
    title_inspiration_service.delete_title_inspiration(db, inspiration_id)
    return success({"id": inspiration_id})
