"""大任务状态聚合（TASK-0403）。

每当某个小任务（article）状态变更后，重新统计其所属大任务（writing_task）的
小任务分布，并据此推导大任务的 ``task_status`` 与 ``article_result_status``。

注意：当前 ``writing_task`` 表**没有** total/pending/running/success/failed 等
计数列（与 dev 文档 10.4 的设计不同，以实际模型为准），因此采用「实时 COUNT
按状态分组」推导，不写入冗余计数列。失败数量通过 ``article_result_status``
（partial_success / failed）以及各 article 的 ``status=failed`` 体现。

状态映射（article.status -> 聚合维度）：
- generating                       -> 进行中（in-flight）
- failed                           -> 失败
- pending_review / normal / disabled -> 已生成成功（done）

推导规则（对齐 dev 文档 10.4，按实际状态集调整）：
- in-flight > 0                    -> task=running,    result=generating
- in-flight == 0 且 failed == 0    -> task=completed,  result=all_success
- in-flight == 0 且 done == 0      -> task=failed,     result=failed
- 其余（有成功也有失败）           -> task=completed,  result=partial_success

大任务处于 cancelled 终态时不再被聚合覆盖。
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.article import Article
from app.models.writing_task import WritingTask
from app.schemas.article import ArticleStatus
from app.schemas.writing_task import ArticleResultStatus, TaskStatus

# 已生成成功（终态/人工可控态）的 article 状态集合
_DONE_STATUSES = {
    ArticleStatus.PENDING_REVIEW.value,
    ArticleStatus.NORMAL.value,
    ArticleStatus.DISABLED.value,
}


def refresh_task_status(
    task_id: int,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
) -> WritingTask | None:
    """重新聚合并落库大任务状态。返回更新后的任务（不存在/已取消则返回原值或 None）。

    使用独立短事务执行，避免与文章生成的长流程共享事务。
    """
    db = session_factory()
    try:
        task = db.execute(
            select(WritingTask).where(
                WritingTask.id == task_id,
                WritingTask.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if task is None:
            return None
        # 已取消为终态，不被聚合覆盖
        if task.task_status == TaskStatus.CANCELLED.value:
            return task

        rows = db.execute(
            select(Article.status, func.count())
            .where(
                Article.writing_task_id == task_id,
                Article.is_deleted.is_(False),
            )
            .group_by(Article.status)
        ).all()

        counts = {status: count for status, count in rows}
        total = sum(counts.values())
        if total == 0:
            return task

        in_flight = counts.get(ArticleStatus.GENERATING.value, 0)
        failed = counts.get(ArticleStatus.FAILED.value, 0)
        done = sum(counts.get(s, 0) for s in _DONE_STATUSES)

        if in_flight > 0:
            task.task_status = TaskStatus.RUNNING.value
            task.article_result_status = ArticleResultStatus.GENERATING.value
        elif failed == 0:
            task.task_status = TaskStatus.COMPLETED.value
            task.article_result_status = ArticleResultStatus.ALL_SUCCESS.value
        elif done == 0:
            task.task_status = TaskStatus.FAILED.value
            task.article_result_status = ArticleResultStatus.FAILED.value
        else:
            task.task_status = TaskStatus.COMPLETED.value
            task.article_result_status = ArticleResultStatus.PARTIAL_SUCCESS.value

        db.commit()
        db.refresh(task)
        return task
    finally:
        db.close()
