"""画像图库图片 Schema。

字段严格对齐 docs/api-contract.md：
    id, category_id, image_url, use_count, created_at, updated_at

use_count 为系统维护的统计字段，仅在响应中返回，不接受新增/编辑写入。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ImageAssetCreate(BaseModel):
    """新增图片请求体。"""

    category_id: int = Field(..., ge=1, description="所属图库分类 ID")
    image_url: str = Field(..., description="图片 URL")

    @field_validator("image_url")
    @classmethod
    def image_url_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("image_url 不能为空")
        return v


class ImageAssetUpdate(BaseModel):
    """编辑图片请求体。所有字段可选，仅更新提供的字段。"""

    category_id: int | None = Field(default=None, ge=1, description="所属图库分类 ID")
    image_url: str | None = Field(default=None, description="图片 URL")

    @field_validator("image_url")
    @classmethod
    def image_url_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("image_url 不能为空")
        return v


class ImageAssetOut(BaseModel):
    """图片响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    image_url: str
    use_count: int
    created_at: datetime
    updated_at: datetime
