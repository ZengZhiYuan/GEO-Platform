"""文章（小任务）基础 Schema。

字段严格对齐 docs/api-contract.md：
    id, writing_task_id, article_title, cover_image_url, status, content,
    error_message, created_at, updated_at

本任务（TASK-0305）仅提供小任务的基础输出 Schema 与状态枚举；
文章的编辑 / 状态切换请求 Schema 由文章清单模块（TASK-0307）补充。
请求/响应统一使用 snake_case，不做字段名转换。
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ArticleStatus(StrEnum):
    """文章状态枚举（见 docs/api-contract.md 文章清单 status）。"""

    GENERATING = "generating"          # 生成中
    PENDING_REVIEW = "pending_review"  # 待审核
    NORMAL = "normal"                  # 正常
    DISABLED = "disabled"              # 禁用
    FAILED = "failed"                  # 生成失败


class ArticleOut(BaseModel):
    """文章响应体（基础）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    writing_task_id: int
    article_title: str | None = None
    cover_image_url: str | None = None
    status: str
    content: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
