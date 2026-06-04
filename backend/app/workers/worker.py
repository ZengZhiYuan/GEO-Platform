"""Dramatiq Worker 启动入口。

启动命令（在 backend/ 目录、已激活虚拟环境、Redis 已就绪时）：

    dramatiq app.workers.worker

Windows 下建议显式指定进程 / 线程数（Dramatiq 在 Windows 用 spawn 多进程）：

    dramatiq app.workers.worker --processes 1 --threads 4

导入本模块会：
1. 通过 ``app.workers.broker`` 设置全局 Dramatiq broker；
2. 导入 ``app.tasks.article_tasks`` 以向 broker 注册所有 actor。
Dramatiq CLI 据此发现并消费任务。
"""

from __future__ import annotations

# 1) 先设置全局 broker（务必在导入 actor 之前）
from app.workers.broker import broker  # noqa: F401

# 2) 导入任务模块以注册 actor
import app.tasks.article_tasks  # noqa: E402,F401
from app.tasks.article_tasks import generate_article  # noqa: E402

__all__ = ["broker", "generate_article"]
