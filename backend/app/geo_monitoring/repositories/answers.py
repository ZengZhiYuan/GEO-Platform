"""答案、引用与品牌识别结果仓储。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.geo_monitoring.models import Answer, AnswerBrandResult, AnswerCitation


# 按 ID 查询答案，并预加载引用与品牌识别结果
def get_by_id(db: Session, answer_id: int) -> Answer | None:
    return db.execute(
        select(Answer)
        .options(
            selectinload(Answer.citations),
            selectinload(Answer.brand_results),
        )
        .where(Answer.id == answer_id, Answer.is_deleted.is_(False))
    ).scalar_one_or_none()


# 按查询任务 ID 查询关联答案
def get_by_task_id(db: Session, task_id: int) -> Answer | None:
    return db.execute(
        select(Answer).where(
            Answer.task_id == task_id,
            Answer.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


# 分页查询指定运行下的答案列表
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
    # 通过 QueryTask 关联统计与分页
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


# 将答案实体加入当前会话
def add(db: Session, answer: Answer) -> None:
    db.add(answer)


# 将答案引用实体加入当前会话
def add_citation(db: Session, citation: AnswerCitation) -> None:
    db.add(citation)


# 将答案品牌识别结果实体加入当前会话
def add_brand_result(db: Session, brand_result: AnswerBrandResult) -> None:
    db.add(brand_result)


# 统计指定查询任务下的答案数量
def count_by_task_id(db: Session, task_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Answer)
            .where(Answer.task_id == task_id, Answer.is_deleted.is_(False))
        )
        or 0
    )
