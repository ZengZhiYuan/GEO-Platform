"""文章模型。

对应数据表 ``article``（见 docs/api-contract.md 文章清单）。
文章为写作大任务拆分出的小任务生成结果，由写作任务/Worker 模块写入，
本任务（TASK-0307）仅提供清单查询、详情、内容编辑与状态切换接口。
公共字段（id / created_at / updated_at / 软删除 / 租户等）继承自 BaseModel。

字段命名以 docs/api-contract.md 为唯一权威源：
    writing_task_id / article_title / cover_image_url / status / content / error_message

沿用代码库无 DB 外键约定：``writing_task_id`` 仅建索引，引用完整性在 service 层校验。
``content`` 存储富文本 HTML 或 JSON 字符串，统一用 Text。
"""

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Article(BaseModel):
    """文章清单。管理所有小任务生成出来的文章。"""

    __tablename__ = "article"

    # 所属写作大任务 ID，无 DB 外键，仅建索引，service 层校验引用完整性
    writing_task_id: Mapped[int] = mapped_column(
        BigInteger, index=True, nullable=False
    )
    # 文章标题，生成中可能为空
    article_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 封面图 URL，生成中可能为空
    cover_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 文章状态：generating / pending_review / normal / disabled / failed
    status: Mapped[str] = mapped_column(
        String(32), server_default="generating", default="generating", nullable=False
    )
    # 正文内容，支持富文本 HTML 或 JSON 字符串，生成中可能为空
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 生成失败时的错误信息
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
