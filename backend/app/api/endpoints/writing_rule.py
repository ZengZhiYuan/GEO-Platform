"""写作规范 API Router。

路径前缀由 app/api/router.py include 时指定（最终为 /api/writing-rules）。
所有接口返回统一响应格式：{"code": 0, "message": "success", "data": ...}
"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.schemas.writing_rule import (
    CreationType,
    WritingRuleCreate,
    WritingRuleOut,
    WritingRuleUpdate,
)
from app.services import writing_rule as writing_rule_service

router = APIRouter(prefix="/writing-rules", tags=["写作规范"])


@router.get("", summary="分页查询写作规范")
def list_writing_rules(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    rule_name: str | None = Query(None, description="按规范名称模糊搜索"),
    creation_type: CreationType | None = Query(None, description="按创作类型筛选"),
    db: Session = Depends(get_db),
) -> dict:
    items, total = writing_rule_service.list_writing_rules(
        db,
        page=page,
        page_size=page_size,
        rule_name=rule_name,
        creation_type=creation_type.value if creation_type else None,
    )
    data = [
        WritingRuleOut.model_validate(item).model_dump(mode="json") for item in items
    ]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("", summary="新增写作规范")
def create_writing_rule(
    payload: WritingRuleCreate,
    db: Session = Depends(get_db),
) -> dict:
    rule = writing_rule_service.create_writing_rule(db, payload)
    return success(WritingRuleOut.model_validate(rule).model_dump(mode="json"))


@router.get("/{rule_id}", summary="获取写作规范详情")
def get_writing_rule(
    rule_id: int = Path(..., ge=1, description="写作规范 ID"),
    db: Session = Depends(get_db),
) -> dict:
    rule = writing_rule_service.get_writing_rule(db, rule_id)
    return success(WritingRuleOut.model_validate(rule).model_dump(mode="json"))


@router.put("/{rule_id}", summary="更新写作规范")
def update_writing_rule(
    payload: WritingRuleUpdate,
    rule_id: int = Path(..., ge=1, description="写作规范 ID"),
    db: Session = Depends(get_db),
) -> dict:
    rule = writing_rule_service.update_writing_rule(db, rule_id, payload)
    return success(WritingRuleOut.model_validate(rule).model_dump(mode="json"))


@router.delete("/{rule_id}", summary="删除写作规范")
def delete_writing_rule(
    rule_id: int = Path(..., ge=1, description="写作规范 ID"),
    db: Session = Depends(get_db),
) -> dict:
    writing_rule_service.delete_writing_rule(db, rule_id)
    return success({"id": rule_id})
