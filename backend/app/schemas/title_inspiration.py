"""标题灵感 Schema。

字段严格对齐 docs/api-contract.md：
    id, main_word, question, collect_status, created_at, updated_at

请求/响应统一使用 snake_case，不做字段名转换。
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CollectStatus(StrEnum):
    """收录状态枚举（对应 docs/claude-code-dev.md 16.1 收录状态字典）。"""

    NOT_INCLUDED = "not_included"
    INCLUDED = "included"


class TitleInspirationCreate(BaseModel):
    """新增标题灵感请求体。"""

    main_word: str = Field(..., max_length=255, description="主词（关键词名称）")
    question: str = Field(..., description="围绕主词的提问/选题问题")
    collect_status: CollectStatus = Field(
        default=CollectStatus.NOT_INCLUDED, description="收录状态"
    )

    @field_validator("main_word")
    @classmethod
    def main_word_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("main_word 不能为空")
        return v

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question 不能为空")
        return v


class TitleInspirationUpdate(BaseModel):
    """编辑标题灵感请求体。所有字段可选，仅更新提供的字段。"""

    main_word: str | None = Field(default=None, max_length=255, description="主词")
    question: str | None = Field(default=None, description="问题")
    collect_status: CollectStatus | None = Field(default=None, description="收录状态")

    @field_validator("main_word")
    @classmethod
    def main_word_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("main_word 不能为空")
        return v

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("question 不能为空")
        return v


class TitleInspirationOut(BaseModel):
    """标题灵感响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    main_word: str
    question: str
    collect_status: str
    created_at: datetime
    updated_at: datetime
