"""答案 API。"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.schemas import AnswerDetailRead, AnswerRead
from app.geo_monitoring.services import answers as answer_service

router = APIRouter()


@router.get("/runs/{run_id}/answers", summary="分页查询运行答案")
def list_run_answers(
    run_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    items, total = answer_service.list_run_answers(
        db, run_id=run_id, page=page, page_size=page_size
    )
    data = [AnswerRead.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.get("/answers/{answer_id}", summary="获取答案详情")
def get_answer(
    answer_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    answer = answer_service.get_answer_detail(db, answer_id)
    return success(answer.model_dump(mode="json"))
