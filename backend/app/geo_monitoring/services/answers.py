"""答案采集结果服务。"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import Answer
from app.geo_monitoring.repositories import answers as answer_repo
from app.geo_monitoring.repositories import runs as run_repo
from app.geo_monitoring.schemas import AnswerCreate, AnswerDetailRead


# 按 ID 查询答案，不存在则抛业务异常
def get_answer(db: Session, answer_id: int) -> Answer:
    answer = answer_repo.get_by_id(db, answer_id)
    if answer is None:
        raise BusinessException(message="答案不存在", code=40400)
    return answer


# 获取答案详情 DTO
def get_answer_detail(db: Session, answer_id: int) -> AnswerDetailRead:
    return AnswerDetailRead.model_validate(get_answer(db, answer_id))


# 分页列出某次运行下的答案
def list_run_answers(
    db: Session,
    *,
    run_id: int,
    page: int,
    page_size: int,
) -> tuple[list[Answer], int]:
    if run_repo.get_by_id(db, run_id) is None:
        raise BusinessException(message="监测运行不存在", code=40400)
    return answer_repo.list_by_run_id(
        db, run_id=run_id, page=page, page_size=page_size
    )


# 创建答案记录，同一任务幂等返回已有答案
def create_answer(db: Session, payload: AnswerCreate) -> Answer:
    existing = answer_repo.get_by_task_id(db, payload.task_id)
    if existing is not None:
        return existing

    answer = Answer(**payload.model_dump())
    try:
        answer_repo.add(db, answer)
        db.commit()
    except IntegrityError:
        # 并发写入冲突时回滚并尝试返回已存在记录
        db.rollback()
        existing = answer_repo.get_by_task_id(db, payload.task_id)
        if existing is not None:
            return existing
        raise BusinessException(message="答案写入冲突", code=40904, status_code=409)
    db.refresh(answer)
    return answer
