"""写作任务 Schema。

字段严格对齐 docs/api-contract.md：
    id, task_name, content_category_id, distill_keywords, image_category_id,
    article_image_count, brand_knowledge_id, content_rule_id, title_rule_id,
    article_result_status, ai_generate_count, task_status, created_at, updated_at

article_result_status / task_status 为系统维护字段，仅在响应中返回，
不接受新增写入（创建时由 service 设置初始值）。
请求/响应统一使用 snake_case，不做字段名转换。
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskStatus(StrEnum):
    """大任务状态枚举（见 docs/api-contract.md 写作任务 task_status）。"""

    DRAFT = "draft"          # 草稿
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 执行失败
    CANCELLED = "cancelled"  # 已取消


class ArticleResultStatus(StrEnum):
    """文章结果聚合状态枚举（大任务维度的文章生成结果）。"""

    NOT_GENERATED = "not_generated"      # 未生成
    GENERATING = "generating"            # 生成中
    ALL_SUCCESS = "all_success"          # 全部成功
    PARTIAL_SUCCESS = "partial_success"  # 部分成功
    FAILED = "failed"                    # 全部失败


class WritingTaskCreate(BaseModel):
    """新增写作任务请求体。

    根据 ai_generate_count 自动拆分对应数量的小任务。
    article_result_status / task_status 为系统维护，不在请求体中。
    """

    task_name: str = Field(..., max_length=255, description="任务名称")
    content_category_id: int = Field(..., ge=1, description="文章分类 ID")
    distill_keywords: str = Field(..., max_length=255, description="蒸馏训练词")
    image_category_id: int | None = Field(
        default=None, ge=1, description="画像图库分类 ID（可选）"
    )
    article_image_count: int = Field(
        default=0, ge=0, le=100, description="文章配图数量"
    )
    brand_knowledge_id: int | None = Field(
        default=None, ge=1, description="品牌知识库 ID（可选）"
    )
    content_rule_id: int = Field(..., ge=1, description="内容创作指令 ID")
    title_rule_id: int | None = Field(
        default=None, ge=1, description="标题创作指令 ID（可选）"
    )
    ai_generate_count: int = Field(
        ..., ge=1, le=100, description="AI 创作数量，决定拆分的小任务数量"
    )

    @field_validator("task_name", "distill_keywords")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("不能为空")
        return v


class WritingTaskOut(BaseModel):
    """写作任务响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_name: str
    content_category_id: int
    distill_keywords: str
    image_category_id: int | None = None
    article_image_count: int
    brand_knowledge_id: int | None = None
    content_rule_id: int
    title_rule_id: int | None = None
    article_result_status: str
    ai_generate_count: int
    task_status: str
    created_at: datetime
    updated_at: datetime
