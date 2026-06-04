"""内容分类 Schema。

字段严格对齐 docs/api-contract.md：
    id, group_name, article_count, created_at, updated_at

article_count 为系统维护的统计字段，仅在响应中返回，不接受新增/编辑写入
（与关键词库 question_count、图库 image_count 的处理保持一致）。
请求/响应统一使用 snake_case，不做字段名转换。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContentCategoryCreate(BaseModel):
    """新增内容分类请求体。"""

    group_name: str = Field(..., max_length=255, description="分组名称")

    @field_validator("group_name")
    @classmethod
    def group_name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("group_name 不能为空")
        return v


class ContentCategoryUpdate(BaseModel):
    """编辑内容分类请求体。所有字段可选，仅更新提供的字段。"""

    group_name: str | None = Field(default=None, max_length=255, description="分组名称")

    @field_validator("group_name")
    @classmethod
    def group_name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("group_name 不能为空")
        return v


class ContentCategoryOut(BaseModel):
    """内容分类响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    group_name: str
    article_count: int
    created_at: datetime
    updated_at: datetime
