"""画像图库分类 Schema。

字段严格对齐 docs/api-contract.md：
    id, category_name, image_count, created_at, updated_at

image_count 为系统维护的统计字段，仅在响应中返回，不接受新增/编辑写入
（与关键词库 question_count 的处理保持一致）。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ImageCategoryCreate(BaseModel):
    """新增图库分类请求体。"""

    category_name: str = Field(..., max_length=255, description="分类名称")

    @field_validator("category_name")
    @classmethod
    def category_name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("category_name 不能为空")
        return v


class ImageCategoryUpdate(BaseModel):
    """编辑图库分类请求体。所有字段可选，仅更新提供的字段。"""

    category_name: str | None = Field(
        default=None, max_length=255, description="分类名称"
    )

    @field_validator("category_name")
    @classmethod
    def category_name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("category_name 不能为空")
        return v


class ImageCategoryOut(BaseModel):
    """图库分类响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category_name: str
    image_count: int
    created_at: datetime
    updated_at: datetime
