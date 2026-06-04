"""文章 Schema。

字段严格对齐 docs/api-contract.md：
    id, writing_task_id, article_title, cover_image_url, status,
    content, error_message, created_at, updated_at

请求/响应统一使用 snake_case，不做字段名转换。

说明：
- 文章由写作任务/Worker 生成，本任务不提供新增接口。
- 编辑接口（PUT）仅允许修改 article_title / cover_image_url / content，
  状态变更走独立的状态切换接口（POST /api/articles/{id}/status）。
- 状态切换仅允许人工可控的目标态：pending_review / normal / disabled / failed
  （generating 为系统生成中状态，不作为人工切换目标）。
- content 支持富文本 HTML 或 JSON 字符串。
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ArticleStatus(StrEnum):
    """文章状态枚举（见 docs/api-contract.md 文章清单 status 枚举）。"""

    GENERATING = "generating"
    PENDING_REVIEW = "pending_review"
    NORMAL = "normal"
    DISABLED = "disabled"
    FAILED = "failed"


class ArticleSwitchStatus(StrEnum):
    """状态切换接口允许的人工目标态（不含系统态 generating）。"""

    PENDING_REVIEW = "pending_review"
    NORMAL = "normal"
    DISABLED = "disabled"
    FAILED = "failed"


class ArticleUpdate(BaseModel):
    """编辑文章请求体。所有字段可选，仅更新提供的字段。

    仅允许编辑标题、封面图 URL、正文内容；状态变更请使用状态切换接口。
    """

    article_title: str | None = Field(
        default=None, max_length=500, description="文章标题"
    )
    cover_image_url: str | None = Field(default=None, description="封面图 URL")
    content: str | None = Field(default=None, description="正文内容（HTML 或 JSON 字符串）")

    @field_validator("article_title")
    @classmethod
    def article_title_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("article_title 不能为空")
        return v


class ArticleStatusUpdate(BaseModel):
    """文章状态切换请求体。"""

    status: ArticleSwitchStatus = Field(..., description="目标状态")


class ArticleOut(BaseModel):
    """文章响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    writing_task_id: int
    article_title: str | None
    cover_image_url: str | None
    status: str
    content: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
