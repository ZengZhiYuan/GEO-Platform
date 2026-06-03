"""关键词库 Schema。

字段严格对齐 docs/api-contract.md：
    id, main_word, question_count, optimize_status, created_at, updated_at

请求/响应统一使用 snake_case，不做字段名转换。
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OptimizeStatus(StrEnum):
    """优化状态枚举（见 docs/claude-code-dev.md 16.2）。"""

    NOT_OPTIMIZED = "not_optimized"
    OPTIMIZING = "optimizing"
    OPTIMIZED = "optimized"


class KeywordCreate(BaseModel):
    """新增关键词请求体。"""

    main_word: str = Field(..., max_length=255, description="主词（关键词名称）")
    optimize_status: OptimizeStatus = Field(
        default=OptimizeStatus.NOT_OPTIMIZED, description="优化状态"
    )

    @field_validator("main_word")
    @classmethod
    def main_word_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("main_word 不能为空")
        return v


class KeywordUpdate(BaseModel):
    """编辑关键词请求体。所有字段可选，仅更新提供的字段。"""

    main_word: str | None = Field(default=None, max_length=255, description="主词")
    optimize_status: OptimizeStatus | None = Field(default=None, description="优化状态")

    @field_validator("main_word")
    @classmethod
    def main_word_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("main_word 不能为空")
        return v


class KeywordOut(BaseModel):
    """关键词响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    main_word: str
    question_count: int
    optimize_status: str
    created_at: datetime
    updated_at: datetime
