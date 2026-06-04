"""写作规范 Schema。

字段严格对齐 docs/api-contract.md：
    id, rule_name, creation_type, instruction_content, created_at, updated_at

请求/响应统一使用 snake_case，不做字段名转换。
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreationType(StrEnum):
    """创作类型枚举（见 docs/api-contract.md 写作规范）。"""

    ARTICLE_CREATION = "article_creation"
    TITLE_CREATION = "title_creation"
    TRAFFIC_REPLICATION = "traffic_replication"


class WritingRuleCreate(BaseModel):
    """新增写作规范请求体。"""

    rule_name: str = Field(..., max_length=255, description="规范名称")
    creation_type: CreationType = Field(..., description="创作类型")
    instruction_content: str = Field(..., description="提示词指令内容")

    @field_validator("rule_name")
    @classmethod
    def rule_name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("rule_name 不能为空")
        return v

    @field_validator("instruction_content")
    @classmethod
    def instruction_content_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("instruction_content 不能为空")
        return v


class WritingRuleUpdate(BaseModel):
    """编辑写作规范请求体。所有字段可选，仅更新提供的字段。"""

    rule_name: str | None = Field(default=None, max_length=255, description="规范名称")
    creation_type: CreationType | None = Field(default=None, description="创作类型")
    instruction_content: str | None = Field(default=None, description="提示词指令内容")

    @field_validator("rule_name")
    @classmethod
    def rule_name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("rule_name 不能为空")
        return v

    @field_validator("instruction_content")
    @classmethod
    def instruction_content_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("instruction_content 不能为空")
        return v


class WritingRuleOut(BaseModel):
    """写作规范响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_name: str
    creation_type: str
    instruction_content: str
    created_at: datetime
    updated_at: datetime
