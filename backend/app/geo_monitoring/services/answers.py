"""答案采集结果服务。"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import Answer, Prompt
from app.geo_monitoring.repositories import answers as answer_repo
from app.geo_monitoring.repositories import runs as run_repo
from app.geo_monitoring.schemas import AnswerCreate, AnswerDetailRead, AnswerRead
from app.geo_monitoring.services.answer_metadata import build_answer_metadata_fields


# 按 ID 查询答案，不存在则抛业务异常
def get_answer(db: Session, answer_id: int) -> Answer:
    answer = answer_repo.get_by_id(db, answer_id)
    if answer is None:
        raise BusinessException(message="答案不存在", code=40400)
    return answer


def _load_prompt_for_answer(db: Session, answer: Answer) -> Prompt:
    prompt = db.execute(
        select(Prompt).where(
            Prompt.id == answer.prompt_id,
            Prompt.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if prompt is None:
        raise BusinessException(message="监测问题不存在", code=40400)
    return prompt


def build_answer_detail_read(db: Session, answer: Answer) -> AnswerDetailRead:
    prompt = _load_prompt_for_answer(db, answer)
    base = AnswerRead.model_validate(answer).model_dump()
    metadata = build_answer_metadata_fields(answer.raw_response_json)
    return AnswerDetailRead(
        **base,
        prompt_text=prompt.prompt_text,
        prompt_type=prompt.prompt_type,
        **metadata,
        citations=answer.citations,
        brand_results=answer.brand_results,
    )


# 获取答案详情 DTO
def get_answer_detail(db: Session, answer_id: int) -> AnswerDetailRead:
    return build_answer_detail_read(db, get_answer(db, answer_id))


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
