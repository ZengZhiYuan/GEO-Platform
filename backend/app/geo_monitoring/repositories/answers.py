"""答案、引用与品牌识别结果仓储。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.geo_monitoring.models import Answer, AnswerBrandResult, AnswerCitation


def get_by_id(db: Session, answer_id: int) -> Answer | None:
    return db.execute(
        select(Answer)
        .options(
            selectinload(Answer.citations),
            selectinload(Answer.brand_results),
        )
        .where(Answer.id == answer_id, Answer.is_deleted.is_(False))
    ).scalar_one_or_none()


def get_by_task_id(db: Session, task_id: int) -> Answer | None:
    return db.execute(
        select(Answer).where(
            Answer.task_id == task_id,
            Answer.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def list_by_run_id(
    db: Session,
    *,
    run_id: int,
    page: int,
    page_size: int,
) -> tuple[list[Answer], int]:
    from app.geo_monitoring.models import QueryTask

    conditions = [
        Answer.is_deleted.is_(False),
        QueryTask.run_id == run_id,
        QueryTask.is_deleted.is_(False),
    ]
    total = db.execute(
        select(func.count())
        .select_from(Answer)
        .join(QueryTask, QueryTask.id == Answer.task_id)
        .where(*conditions)
    ).scalar_one()
    items = list(
        db.execute(
            select(Answer)
            .join(QueryTask, QueryTask.id == Answer.task_id)
            .where(*conditions)
            .order_by(Answer.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


def add(db: Session, answer: Answer) -> None:
    db.add(answer)


def add_citation(db: Session, citation: AnswerCitation) -> None:
    db.add(citation)


def add_brand_result(db: Session, brand_result: AnswerBrandResult) -> None:
    db.add(brand_result)


def count_by_task_id(db: Session, task_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Answer)
            .where(Answer.task_id == task_id, Answer.is_deleted.is_(False))
        )
        or 0
    )
