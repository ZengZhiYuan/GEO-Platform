"""关键词库 API Router。

路径前缀由 app/api/router.py include 时指定（最终为 /api/keywords）。
所有接口返回统一响应格式：{"code": 0, "message": "success", "data": ...}
"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.schemas.keyword import KeywordCreate, KeywordOut, KeywordUpdate, OptimizeStatus
from app.services import keyword as keyword_service

router = APIRouter(prefix="/keywords", tags=["关键词库"])


@router.get("", summary="分页查询关键词")
def list_keywords(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    main_word: str | None = Query(None, description="按主词模糊搜索"),
    optimize_status: OptimizeStatus | None = Query(None, description="按优化状态筛选"),
    db: Session = Depends(get_db),
) -> dict:
    items, total = keyword_service.list_keywords(
        db,
        page=page,
        page_size=page_size,
        main_word=main_word,
        optimize_status=optimize_status.value if optimize_status else None,
    )
    data = [KeywordOut.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("", summary="新增关键词")
def create_keyword(
    payload: KeywordCreate,
    db: Session = Depends(get_db),
) -> dict:
    keyword = keyword_service.create_keyword(db, payload)
    return success(KeywordOut.model_validate(keyword).model_dump(mode="json"))


@router.get("/{keyword_id}", summary="获取关键词详情")
def get_keyword(
    keyword_id: int = Path(..., ge=1, description="关键词 ID"),
    db: Session = Depends(get_db),
) -> dict:
    keyword = keyword_service.get_keyword(db, keyword_id)
    return success(KeywordOut.model_validate(keyword).model_dump(mode="json"))


@router.put("/{keyword_id}", summary="更新关键词")
def update_keyword(
    payload: KeywordUpdate,
    keyword_id: int = Path(..., ge=1, description="关键词 ID"),
    db: Session = Depends(get_db),
) -> dict:
    keyword = keyword_service.update_keyword(db, keyword_id, payload)
    return success(KeywordOut.model_validate(keyword).model_dump(mode="json"))


@router.delete("/{keyword_id}", summary="删除关键词")
def delete_keyword(
    keyword_id: int = Path(..., ge=1, description="关键词 ID"),
    db: Session = Depends(get_db),
) -> dict:
    keyword_service.delete_keyword(db, keyword_id)
    return success({"id": keyword_id})
