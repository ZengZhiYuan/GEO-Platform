"""异步任务包（Dramatiq actor + 编排 + 大任务状态聚合）。

对外导出：
- ``generate_article``：文章生成 actor（Dramatiq 消费入口）。
- ``enqueue_article_generation`` / ``enqueue_articles``：投递小任务到 MQ。
- ``refresh_task_status``：大任务状态聚合（TASK-0403）。
"""

from app.tasks.aggregation import refresh_task_status
from app.tasks.article_tasks import (
    enqueue_article_generation,
    enqueue_articles,
    generate_article,
)

__all__ = [
    "enqueue_article_generation",
    "enqueue_articles",
    "generate_article",
    "refresh_task_status",
]
